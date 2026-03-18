import datetime as dt
import polars as pl
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

from src.manager.database.factors import get_factors_data
from src.manager.database.stock_return import get_stock_return


def preprocess_factors(df: pl.DataFrame) -> pl.DataFrame:
    # 选出因子列：排除标识列
    exclude_cols = ["stkcd", "accper"]
    factor_cols = [c for c in df.columns if c not in exclude_cols]

    # 1. 截面标准化：按 accper 分组，对每个因子做 (x - mean) / std
    df = df.with_columns(
        [
            (
                (pl.col(col) - pl.col(col).mean().over("accper"))
                / pl.col(col).std().over("accper")
            ).alias(col)
            for col in factor_cols
        ]
    )

    # 2. 缺失值填充：
    # 2.1 按证券和时间排序
    df = df.sort(["stkcd", "accper"])

    # 2.2 对每个证券，使用之前的值向前填充
    df = df.with_columns(
        [
            pl.col(col).forward_fill().over("stkcd").alias(col)
            for col in factor_cols
        ]
    )

    # 2.3 仍为缺失 / 非数值的情况处理（比如整只股票都缺某个因子、或标准化除以 0 得到 NaN）
    df = df.with_columns(
        [
            pl.col(col)
            .fill_null(0)   # null -> 0
            .fill_nan(0)    # NaN -> 0（防止 std 为 0 导致 NaN）
            .alias(col)
            for col in factor_cols
        ]
    )

    return df


def main() -> None:
    # 加载所有证券 2004-01-01 至 2024-12-31 的因子数据
    start_date = dt.date(2004, 1, 1)
    end_date = dt.date(2024, 12, 31)

    # code_list 传空列表，表示所有证券
    factors_df = get_factors_data(
        code_list=[],
        start_date=start_date,
        end_date=end_date,
    )

    print("原始因子数据：")
    print(factors_df.head())
    print(f"\nshape = {factors_df.shape}")

    # 预处理：截面标准化 + 缺失值填充
    factors_df = preprocess_factors(factors_df)

    print("\n预处理后的因子数据：")
    print(factors_df.head())
    print(f"\nshape = {factors_df.shape}")

    # ==============================
    # 读取并处理收益率（下月收益）
    # ==============================
    # 如果 code_list 为空，使用因子表中的所有证券代码
    all_codes = factors_df["stkcd"].unique().to_list()

    returns_df = get_stock_return(
        code_list=all_codes,
        start_date=start_date,
        end_date=end_date,
    )

    # 假设收益率列名为 'ret'，如果不一致可以根据实际列名修改
    # 将收益的月份在原列上 +1 个月，用来表示「下一期收益」
    returns_df = returns_df.with_columns(
        pl.col("accper").dt.offset_by("1mo")
    )

    # 只保留用于 join 的列
    returns_df = returns_df.select(["stkcd", "accper", "monthly_return"])

    # 与因子表按照 (stkcd, accper) 连接
    factors_with_ret = factors_df.join(
        returns_df,
        on=["stkcd", "accper"],
        how="left",
    )

    # 剔除收益为空的行
    factors_with_ret = factors_with_ret.drop_nulls(subset=["monthly_return"])

    print("\n连接下月收益后的数据：")
    print(factors_with_ret.head())
    print(f"\nshape = {factors_with_ret.shape}")

    # ==============================
    # 单期特征的 MLP 回归模型
    # ==============================
    # 特征列：除去标识列和标签列
    exclude_cols = ["stkcd", "accper", "monthly_return"]
    feature_cols = [c for c in factors_with_ret.columns if c not in exclude_cols]

    # 随机划分训练 / 测试集：将 20% 的观测随机作为测试集
    rng = np.random.default_rng(42)
    indices = np.arange(factors_with_ret.height)
    rng.shuffle(indices)
    split_idx = int(0.8 * len(indices))
    train_idx = indices[:split_idx]
    test_idx = indices[split_idx:]

    pdf = factors_with_ret.to_pandas()
    X_all = pdf[feature_cols].to_numpy(dtype=np.float32)
    y_all = pdf["monthly_return"].to_numpy(dtype=np.float32)

    X_train = X_all[train_idx]
    y_train = y_all[train_idx]
    X_test = X_all[test_idx]
    y_test = y_all[test_idx]

    # 标签整体统计量与均值基线
    ret_mean = float(y_all.mean())
    ret_std = float(y_all.std())
    baseline_pred = np.full_like(y_all, ret_mean)
    baseline_mse = float(((y_all - baseline_pred) ** 2).mean())

    print("\n===== 标签 monthly_return 统计 =====")
    print(f"mean = {ret_mean:.6f}, std = {ret_std:.6f}")
    print(f"baseline MSE (always predict mean) = {baseline_mse:.6f}")

    class ReturnDataset(Dataset):
        def __init__(self, X: np.ndarray, y: np.ndarray):
            self.X = torch.from_numpy(X).float()
            self.y = torch.from_numpy(y).float().view(-1, 1)

        def __len__(self) -> int:
            return self.X.shape[0]

        def __getitem__(self, idx: int):
            return self.X[idx], self.y[idx]

    train_ds = ReturnDataset(X_train, y_train)
    test_ds = ReturnDataset(X_test, y_test)

    batch_size = 1024
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    input_dim = X_train.shape[1]

    class MLP(nn.Module):
        def __init__(self, input_dim: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 256),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 1),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MLP(input_dim=input_dim).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=5e-5)

    num_epochs = 40
    best_test_loss = float("inf")
    best_r2 = float("nan")

    for epoch in range(1, num_epochs + 1):
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            preds = model(X_batch)
            loss = criterion(preds, y_batch)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * X_batch.size(0)

        train_loss /= len(train_ds)

        # 测试集评估
        model.eval()
        test_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in test_loader:
                X_batch = X_batch.to(device)
                y_batch = y_batch.to(device)
                preds = model(X_batch)
                loss = criterion(preds, y_batch)
                test_loss += loss.item() * X_batch.size(0)

        test_loss /= len(test_ds)
        r2 = 1.0 - test_loss / baseline_mse if baseline_mse > 0 else float("nan")

        if test_loss < best_test_loss:
            best_test_loss = test_loss
            best_r2 = r2

        print(
            f"Epoch {epoch}: train_loss={train_loss:.6f}, "
            f"test_loss={test_loss:.6f}, R2_vs_mean={r2:.4f}"
        )

    print(f"\nBest test_loss={best_test_loss:.6f}, Best R2_vs_mean={best_r2:.4f}")


if __name__ == "__main__":
    main()


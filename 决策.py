import datetime as dt
from typing import Tuple, Dict, Any

import numpy as np
import polars as pl
import torch
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback

from src.manager.database.factors import get_factors_data
from src.manager.database.stock_return import get_stock_return


def preprocess_factors(df: pl.DataFrame) -> Tuple[pl.DataFrame, list[str]]:
    exclude_cols = ["stkcd", "accper"]
    factor_cols = [c for c in df.columns if c not in exclude_cols]

    df = df.with_columns(
        [
            (
                (pl.col(col) - pl.col(col).mean().over("accper"))
                / pl.col(col).std().over("accper")
            ).alias(col)
            for col in factor_cols
        ]
    )

    df = df.sort(["stkcd", "accper"])

    df = df.with_columns(
        [
            pl.col(col).forward_fill().over("stkcd").alias(col)
            for col in factor_cols
        ]
    )

    df = df.with_columns(
        [
            pl.col(col)
            .fill_null(0)
            .fill_nan(0)
            .alias(col)
            for col in factor_cols
        ]
    )

    return df, factor_cols


class PrintStepCallback(BaseCallback):
    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.step_count = 0

    def _on_step(self) -> bool:
        self.step_count += 1
        if self.step_count % 1000 == 0:
            rewards = self.locals.get("rewards", None)
            if rewards is not None:
                avg_r = float(np.mean(rewards))
                print(
                    f"total_steps={self.num_timesteps}, "
                    f"step_in_call={self.step_count}, "
                    f"last_reward_mean={avg_r:.6f}"
                )
            else:
                print(
                    f"total_steps={self.num_timesteps}, "
                    f"step_in_call={self.step_count}"
                )
        return True


class FactorSingleStepEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, X: np.ndarray, y: np.ndarray):
        super().__init__()
        assert X.shape[0] == y.shape[0]

        self.X = X.astype(np.float32)
        self.y = y.astype(np.float32)
        self.n_samples, self.n_features = self.X.shape

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.n_features,),
            dtype=np.float32,
        )
        self.action_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(1,),
            dtype=np.float32,
        )

        self._idx = 0

    def reset(self, *, seed: int | None = None, options: Dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._idx = self.np_random.integers(0, self.n_samples)
        obs = self.X[self._idx]
        return obs, {}

    def step(self, action: np.ndarray):
        a = float(np.clip(action[0], 0.0, 1.0))
        r = float(self.y[self._idx])
        reward = a * r

        terminated = True
        truncated = False
        info = {"raw_return": r, "action": a}

        obs = self.X[self.np_random.integers(0, self.n_samples)]
        return obs, reward, terminated, truncated, info


def build_factors_with_return(
    start_date: dt.date, end_date: dt.date
) -> Tuple[pl.DataFrame, list[str]]:
    factors_df = get_factors_data(
        code_list=[],
        start_date=start_date,
        end_date=end_date,
    )

    factors_df, factor_cols = preprocess_factors(factors_df)

    all_codes = factors_df["stkcd"].unique().to_list()
    returns_df = get_stock_return(
        code_list=all_codes,
        start_date=start_date,
        end_date=end_date,
    )

    returns_df = returns_df.with_columns(
        pl.col("accper").dt.offset_by("1mo")
    )

    returns_df = returns_df.select(["stkcd", "accper", "monthly_return"])

    factors_with_ret = factors_df.join(
        returns_df,
        on=["stkcd", "accper"],
        how="left",
    ).drop_nulls(subset=["monthly_return"])

    factors_with_ret = factors_with_ret.sort(["accper", "stkcd"])

    return factors_with_ret, factor_cols


def evaluate_policy_on_month(
    model: PPO, env: gym.Env, n_episodes: int = 1000
) -> float:
    """在给定月份的环境上评估当前策略的平均奖励。

    注意：这里的 env 是 DummyVecEnv（VecEnv 接口），
    reset() 返回 obs，step() 返回 (obs, rewards, dones, infos)。
    """
    total_reward = 0.0
    n = 0
    for _ in range(n_episodes):
        obs = env.reset()  # (n_envs, obs_dim)
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, rewards, dones, infos = env.step(action)
            # rewards 是 shape (n_envs,) 的数组，这里取均值作为单步奖励
            r = float(np.mean(rewards))
            total_reward += r
            n += 1
            done = bool(np.all(dones))
    return total_reward / max(n, 1)


def main() -> None:
    start_date = dt.date(2004, 1, 1)
    end_date = dt.date(2024, 12, 31)

    factors_with_ret, factor_cols = build_factors_with_return(
        start_date=start_date,
        end_date=end_date,
    )

    print("因子 + 下月收益数据：")
    print(factors_with_ret.head())
    print(f"\nshape = {factors_with_ret.shape}")

    unique_months = (
        factors_with_ret["accper"]
        .unique()
        .sort()
        .to_list()
    )

    policy_kwargs = dict(
        net_arch=[128, 64],
    )

    model: PPO | None = None

    for i, month in enumerate(unique_months):
        month_df = factors_with_ret.filter(pl.col("accper") == month)
        if month_df.height == 0:
            continue

        X_month = month_df.select(factor_cols).to_numpy()
        y_month = month_df["monthly_return"].to_numpy()

        env = DummyVecEnv(
            [lambda: FactorSingleStepEnv(X_month, y_month)]
        )

        if model is None:
            model = PPO(
                "MlpPolicy",
                env,
                verbose=0,
                device="cpu",
                learning_rate=3e-4,
                n_steps=2048,
                batch_size=256,
                gamma=1.0,
                policy_kwargs=policy_kwargs,
            )
        else:
            model.set_env(env)

        n_timesteps = min(50_000, X_month.shape[0] * 20)
        callback = PrintStepCallback()
        model.learn(
            total_timesteps=int(n_timesteps),
            reset_num_timesteps=False,
            callback=callback,
        )

        avg_reward = evaluate_policy_on_month(model, env, n_episodes=500)
        print(f"Month {month}: avg_reward = {avg_reward:.6f}")


if __name__ == "__main__":
    main()


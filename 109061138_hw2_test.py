import sys
import warnings

from pathlib import Path
from collections import deque
from time import perf_counter
from typing import List, Dict

script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

import cv2
import torch
import numpy as np
import numpy.typing as npt
import gym_super_mario_bros

from tqdm import tqdm
from nes_py.wrappers import JoypadSpace
from gym_super_mario_bros.actions import COMPLEX_MOVEMENT

from mario import MarioDDQN

warnings.filterwarnings("ignore", message=".*SuperMarioBros.*-v0.*")

checkpoisnts_dir = script_dir / "checkpoints_202404050135"


class Agent:
    obs_dim = (240, 256, 3)
    action_dim = 7
    n_frames_skip = 4
    n_stacks = 4
    shape = (84, 84)
    epsilon = 0.2

    def __init__(self):
        self.step_count = 0
        self.current_action = 0
        self.frames = deque(
            [
                np.random.randint(0, 255, self.obs_dim, dtype=np.uint8)
                for _ in range(self.n_stacks)
            ],
            maxlen=self.n_stacks,
        )
        self.net = MarioDDQN(self.action_dim, 512).float()

        self.load(script_dir / "109061138_hw2_data")

    def act(self, observation: npt.NDArray) -> int:
        self.frames.append(observation)

        if np.random.rand() < self.epsilon:
            self.current_action = np.random.randint(self.action_dim)
        else:
            obs_stack = self.get_observation()
            obs_tensor = torch.FloatTensor(obs_stack).unsqueeze(0)
            action_values = self.net(obs_tensor, model="online")
            self.current_action = torch.argmax(action_values, axis=1).item()

        self.step_count += 1
        return self.current_action

    def get_observation(self) -> npt.NDArray:
        processed_frames = np.zeros(
            (self.n_stacks, *self.shape), dtype=np.float32
        )

        for i, raw_frame in enumerate(self.frames):
            cropped_frame = raw_frame[32:, :, :]
            gray_frame = cv2.cvtColor(cropped_frame, cv2.COLOR_RGB2GRAY)
            processed_frames[i] = cv2.resize(gray_frame, self.shape)

        return processed_frames

    def load(self, load_path: Path = script_dir / "109061138_hw2_data"):
        if not load_path.exists():
            raise ValueError(f"{load_path} does not exist")

        ckp: Dict = torch.load(
            load_path,
            map_location="cpu",
        )
        exploration_rate = ckp.get("exploration_rate")
        cnns = ckp.get("cnns")
        val_stream = ckp.get("value_stream")
        adv_stream = ckp.get("advantage_stream")

        print(
            f"Loading model at {load_path} with exploration rate {exploration_rate}"
        )
        self.net.cnns.load_state_dict(cnns)
        self.net.val_stream.load_state_dict(val_stream)
        self.net.adv_stream.load_state_dict(adv_stream)
        self.net.sync()
        self.exploration_rate = exploration_rate


def main() -> None:
    env = gym_super_mario_bros.make('SuperMarioBros-v0')
    env = JoypadSpace(env, COMPLEX_MOVEMENT)

    n_episodes = 50
    total_reward = 0.0
    total_time = 0.0
    time_limit = 120.0
    agent = Agent()

    for episode in range(n_episodes):
        obs = env.reset()
        start_time = perf_counter()
        episode_reward = 0.0

        while True:
            action = agent.act(obs)
            obs, reward, done, _ = env.step(action)
            episode_reward += reward
            env.render()

            if perf_counter() - start_time > time_limit:
                print(f"Time limit reached for episode {episode}")
                break

            if done:
                break

        end_time = perf_counter()
        total_time += end_time - start_time
        total_reward += episode_reward
        print(f"Episode {episode + 1} reward: {episode_reward}")

    env.close()
    score = total_reward / 50
    print(f"Final Score: {score}")


if __name__ == '__main__':
    main()
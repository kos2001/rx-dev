"""Check the requested accelerator, then invoke the official LeRobot trainer."""
import runpy
import sys


def check_device(device):
    import torch
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable. Select CPU or use an Apple Silicon training host.")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Select CPU/MPS or use an NVIDIA training host.")


def main():
    device = next(arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--policy.device="))
    check_device(device)
    print(f"Training LeRobot policy on {device}; datasets and weights stay in outputs/.", flush=True)
    runpy.run_module("lerobot.scripts.lerobot_train", run_name="__main__")


if __name__ == "__main__":
    main()

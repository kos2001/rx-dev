"""Compatibility entrypoint; the experiment engine lives in backend."""
from backend.pusht_agent import Planner, PushtEnv, Settings, episode, gym, main, make_env, score, summarize, wrap

if __name__ == "__main__":
    main()

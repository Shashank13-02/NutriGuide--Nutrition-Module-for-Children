"""Compatibility entry point for the corrected task-specific training pipeline.

UNICEF aggregate country surveys do not provide individual diagnostic labels or
image/food annotation pairs. They are not represented as clinical training data.
Training uses reviewed guideline evidence with synthetic selection labels.
"""
from train_model import main

if __name__ == "__main__":
    main()

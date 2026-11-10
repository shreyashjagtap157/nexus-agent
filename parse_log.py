# The Windows tests run `pytest`. Let's assume there is a failure in the tests.
# Wait, look at the job logs:
# pipx 1.18.12 requires filelock>=4.2, but you have filelock 4.0.12 which is incompatible.
# pipx 1.18.12 has requirement filelock>=4.2, but you have filelock 4.0.12.
# ##[error]Process completed with exit code 1.

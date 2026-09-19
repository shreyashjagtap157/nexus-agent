import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").absolute()))
from nexus_agent.core.devops import VerificationPipeline

test_dir = Path("test_workspace")
test_dir.mkdir(exist_ok=True)
(test_dir / "secret.py").write_text("aws_key = 'AKIA1234567890123456'", encoding="utf-8")

pipeline = VerificationPipeline(test_dir)
secrets = pipeline.secret_scanner.scan()
print("secrets:", secrets)

import shutil
shutil.rmtree(test_dir)

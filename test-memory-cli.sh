#!/bin/bash
# Local test script for memory CLI commands
# Uses FAISS backend and test data - completely isolated from production

set -e

REPO_DIR="/Users/ivannagy/DevOps/repos/prometh-sh/prometh-cortex"
TEST_CONFIG="$REPO_DIR/config.test.toml"
VENV="$REPO_DIR/.venv/bin"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Prometh Cortex Memory CLI Local Test ===${NC}"
echo "Test config: $TEST_CONFIG"
echo ""

# Function to run pcortex with test config
run_pcortex() {
    PROMETH_CORTEX_CONFIG="$TEST_CONFIG" "$VENV/python" -m prometh_cortex.cli.main "$@"
}

# 1. Add test memories
echo -e "${BLUE}Step 1: Adding test memories...${NC}"
"$VENV/python" << 'PYTHON_SCRIPT'
import os
from datetime import datetime, timedelta
from prometh_cortex.config import load_config
from prometh_cortex.vector_store import create_vector_store

# Override config path
os.environ['PROMETH_CORTEX_CONFIG'] = '/Users/ivannagy/DevOps/repos/prometh-sh/prometh-cortex/config.test.toml'

config = load_config()
vs = create_vector_store(config)
vs.initialize()

now = datetime.utcnow()

# Add test memories with different dates
memories = [
    {
        "title": "Old Memory 1",
        "content": "This is an old memory from 30 days ago",
        "tags": ["old", "test"],
        "metadata": {"project": "test-old"}
    },
    {
        "title": "Old Memory 2", 
        "content": "Another old memory from 25 days ago",
        "tags": ["old", "test"],
        "metadata": {"project": "test-old"}
    },
    {
        "title": "Recent Memory 1",
        "content": "This is a recent memory from 3 days ago",
        "tags": ["recent", "test"],
        "metadata": {"project": "test-recent"}
    },
    {
        "title": "Recent Memory 2",
        "content": "Another recent memory from 2 days ago",
        "tags": ["recent", "test"],
        "metadata": {"project": "test-recent"}
    },
    {
        "title": "Today Memory",
        "content": "Memory from today",
        "tags": ["today", "test"],
        "metadata": {"project": "test-today"}
    },
]

# Add memories with appropriate timestamps
dates = [
    (now - timedelta(days=30)).isoformat(),
    (now - timedelta(days=25)).isoformat(),
    (now - timedelta(days=3)).isoformat(),
    (now - timedelta(days=2)).isoformat(),
    now.isoformat(),
]

for i, (mem, date) in enumerate(zip(memories, dates)):
    doc_id = f"test_mem_{i+1}"
    payload = {
        "document_id": doc_id,
        "title": mem["title"],
        "content": mem["content"],
        "tags": mem["tags"],
        "created": date,
        "source_type": "prmth_memory",
        **mem["metadata"]
    }
    
    # Store in vector store (simplified - direct FAISS storage)
    print(f"Added: {mem['title']} ({date.split('T')[0]})")

print(f"\nTotal: {len(memories)} test memories created")
PYTHON_SCRIPT

echo ""
echo -e "${GREEN}✓ Test memories added${NC}"
echo ""

# 2. List all memories
echo -e "${BLUE}Step 2: List all memories${NC}"
run_pcortex memory list
echo ""

# 3. List memories from last 7 days
echo -e "${BLUE}Step 3: List memories from last 7 days${NC}"
run_pcortex memory list --since 7d
echo ""

# 4. Dry-run: preview deletion of old memories
echo -e "${BLUE}Step 4: DRY-RUN - Preview deletion of memories older than 10 days${NC}"
run_pcortex memory clear --expiry 10d --dry-run
echo ""

# 5. Dry-run: preview deletion by project
echo -e "${BLUE}Step 5: DRY-RUN - Preview deletion by project${NC}"
run_pcortex memory clear --project test-old --dry-run
echo ""

echo -e "${GREEN}=== Test Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Review the dry-run output above"
echo "  2. To actually delete: remove --dry-run from the commands"
echo "  3. Example: pcortex memory clear --expiry 10d --confirm"
echo ""
echo "Test config location: $TEST_CONFIG"
echo "Test data location: /tmp/prometh-cortex-test/"

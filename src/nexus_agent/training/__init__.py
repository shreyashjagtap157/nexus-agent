"""High-Performance LLM World Model Training Suite.

Implements a Yann LeCun-style Joint Embedding Predictive Architecture (JEPA/LeWorldModel)
with Recurrent-Depth Transformer (RDT), dynamic confidence halting (ACT), and
mechanistic interpretability via Sparse Autoencoders (SAE).
"""

from __future__ import annotations

from nexus_agent.training.data.dataset import StratifiedDataset
from nexus_agent.training.data.ingestion import IngestionManager, WALDatabase
from nexus_agent.training.data.watchdog import DiskWatchdog
from nexus_agent.training.interpretability.hooks import ActivationExtractor
from nexus_agent.training.interpretability.sae import SparseAutoencoder
from nexus_agent.training.model.act import ACTHaltingBlock
from nexus_agent.training.model.jepa import JEPAObjective
from nexus_agent.training.model.losses import TrainingLosses
from nexus_agent.training.model.rdt import RecurrentDepthTransformer
from nexus_agent.training.server.api import create_app
from nexus_agent.training.server.state_machine import TrainingState, TrainingStateMachine

__all__ = [
    "IngestionManager", "WALDatabase",
    "StratifiedDataset", "DiskWatchdog",
    "RecurrentDepthTransformer", "JEPAObjective", "ACTHaltingBlock",
    "TrainingLosses",
    "SparseAutoencoder", "ActivationExtractor",
    "TrainingState", "TrainingStateMachine",
    "create_app",
]

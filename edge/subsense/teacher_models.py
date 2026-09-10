"""SubSense Teacher Models (Full-Precision Baselines).

Includes:
1. Deep Teacher Autoencoder (PyTorch, float32)
   - Deep encoder-decoder (8 -> 64 -> 32 -> 16 -> 32 -> 64 -> 8)
   - Reconstructs expected multi-sensor feature windows
   - Unsupervised training on normal mine operations
   - Reconstruction error thresholding for anomaly detection
2. Teacher Isolation Forest (scikit-learn, full precision)
   - 150 trees, unsupervised ensemble baseline
   - Continuous anomaly scoring and threshold classification
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Dict, Any, Optional


class DeepTeacherAutoencoder(nn.Module):
    """Full-precision deep Autoencoder serving as the cloud-tier teacher baseline."""

    def __init__(self, input_dim: int = 8, latent_dim: int = 16):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, latent_dim),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(x)
        reconstruction = self.decoder(latent)
        return reconstruction

    def compute_reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """Returns MSE reconstruction error per sample."""
        with torch.no_grad():
            x_hat = self.forward(x)
            mse = torch.mean((x - x_hat) ** 2, dim=1)
            return mse


def train_teacher_autoencoder(
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 60,
    batch_size: int = 64,
    lr: float = 1e-3,
    device: str = "cpu",
    seed: int = 42,
) -> Tuple[DeepTeacherAutoencoder, float, Dict[str, Any]]:
    """Train Deep Teacher Autoencoder to convergence on normal operational windows."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Train only on normal windows (unsupervised baseline)
    model = DeepTeacherAutoencoder(input_dim=x_train.shape[1], latent_dim=16).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    criterion = nn.MSELoss()

    tensor_train_x = torch.tensor(x_train, dtype=torch.float32)
    dataset = TensorDataset(tensor_train_x)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model.train()
    history = []
    for epoch in range(epochs):
        epoch_loss = 0.0
        for (batch_x,) in loader:
            batch_x = batch_x.to(device)
            optimizer.zero_grad()
            recon = model(batch_x)
            loss = criterion(recon, batch_x)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(batch_x)
        epoch_loss /= len(tensor_train_x)
        history.append(epoch_loss)

    # Threshold calibration on validation set using percentile-spaced candidates
    model.eval()
    val_x_t = torch.tensor(x_val, dtype=torch.float32).to(device)
    val_errors = model.compute_reconstruction_error(val_x_t).cpu().numpy()

    # Percentile-based search is robust to extreme outlier scales
    thresholds = np.percentile(val_errors, np.linspace(20.0, 99.8, 500))
    best_threshold = float(thresholds[0])
    best_f1 = -1.0
    for th in thresholds:
        preds = (val_errors >= th).astype(int)
        tp = np.sum((preds == 1) & (y_val == 1))
        fp = np.sum((preds == 1) & (y_val == 0))
        fn = np.sum((preds == 0) & (y_val == 1))
        precision = tp / (tp + fp + 1e-9)
        recall = tp / (tp + fn + 1e-9)
        f1 = 2 * precision * recall / (precision + recall + 1e-9)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(th)

    stats = {
        "final_train_loss": history[-1],
        "val_best_f1": best_f1,
        "history": history,
    }
    return model, float(best_threshold), stats


def train_teacher_isolation_forest(
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    n_estimators: int = 150,
    random_state: int = 42,
) -> Tuple[IsolationForest, float, Dict[str, Any]]:
    """Train Teacher Isolation Forest on normal operational windows."""
    iso_forest = IsolationForest(
        n_estimators=n_estimators,
        max_samples=min(512, len(x_train)),
        contamination="auto",
        random_state=random_state,
        n_jobs=-1,
    )
    iso_forest.fit(x_train)

    # Calibrate decision threshold on validation set
    # score_samples returns opposite of anomaly score (lower = more abnormal)
    val_scores = -iso_forest.score_samples(x_val)  # higher = more anomalous

    thresholds = np.percentile(val_scores, np.linspace(20.0, 99.8, 500))
    best_threshold = float(thresholds[0])
    best_f1 = -1.0
    for th in thresholds:
        preds = (val_scores >= th).astype(int)
        tp = np.sum((preds == 1) & (y_val == 1))
        fp = np.sum((preds == 1) & (y_val == 0))
        fn = np.sum((preds == 0) & (y_val == 1))
        precision = tp / (tp + fp + 1e-9)
        recall = tp / (tp + fn + 1e-9)
        f1 = 2 * precision * recall / (precision + recall + 1e-9)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(th)

    stats = {
        "val_best_f1": best_f1,
        "n_estimators": n_estimators,
    }
    return iso_forest, float(best_threshold), stats


def evaluate_classifier(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Calculate recall, false-positive rate (FPR), precision, and F1."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)

    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall + 1e-9)

    return {
        "recall": float(recall),
        "fpr": float(fpr),
        "precision": float(precision),
        "f1": float(f1),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }

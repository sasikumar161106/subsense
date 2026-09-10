import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Optional, List

class AutoencoderNet(nn.Module):
    """Deep bottleneck reconstruction neural network."""

    def __init__(self, input_dim: int = 8, latent_dim: int = 3):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.BatchNorm1d(16),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 8),
            nn.ReLU(),
            nn.Linear(8, 16),
            nn.ReLU(),
            nn.Linear(16, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        x_recon = self.decoder(z)
        return x_recon

class PyTorchAutoencoderDetector:
    """
    Unsupervised Deep Autoencoder Anomaly Detector (Section 4, Table 2).
    Trained strictly on normal-condition sensor windows to reconstruct normal telemetry.
    High MSE reconstruction loss indicates anomalous, non-linear deformation drift.
    """

    def __init__(
        self,
        input_dim: int = 8,
        latent_dim: int = 3,
        learning_rate: float = 0.001,
        epochs: int = 30,
        batch_size: int = 32,
        version: str = "ae-v1.0.0",
        device: Optional[str] = None,
    ):
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.version = version
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        self.model = AutoencoderNet(input_dim=input_dim, latent_dim=latent_dim).to(self.device)
        self.is_fitted = False
        self._mean = np.zeros(input_dim)
        self._std = np.ones(input_dim)
        self._normal_mse_threshold = 1.0

    def fit(self, X: np.ndarray) -> "PyTorchAutoencoderDetector":
        """Fits the Autoencoder on baseline/normal telemetry feature windows."""
        if X.ndim == 1:
            X = X.reshape(-1, self.input_dim)

        self._mean = np.mean(X, axis=0)
        self._std = np.std(X, axis=0) + 1e-6
        X_norm = (X - self._mean) / self._std

        tensor_x = torch.tensor(X_norm, dtype=torch.float32)
        dataset = torch.utils.data.TensorDataset(tensor_x)
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate, weight_decay=1e-5)
        criterion = nn.MSELoss()

        self.model.train()
        for epoch in range(self.epochs):
            for (batch_x,) in loader:
                batch_x = batch_x.to(self.device)
                optimizer.zero_grad()
                recon = self.model(batch_x)
                loss = criterion(recon, batch_x)
                loss.backward()
                optimizer.step()

        self.is_fitted = True

        # Calibrate baseline reconstruction error distribution
        self.model.eval()
        with torch.no_grad():
            full_x = tensor_x.to(self.device)
            full_recon = self.model(full_x)
            mse = torch.mean((full_x - full_recon) ** 2, dim=1).cpu().numpy()
            # Set normal threshold at 95th percentile of normal training reconstruction loss
            self._normal_mse_threshold = float(np.percentile(mse, 95)) + 1e-4

        return self

    def predict_anomaly_score(self, X: np.ndarray) -> np.ndarray:
        """
        Computes normalized anomaly score in [0.0, 1.0].
        Calculates per-sample reconstruction MSE and maps through a smooth sigmoid response.
        """
        if not self.is_fitted:
            # Cold-start heuristic before training
            return np.clip(np.mean(np.abs(X), axis=-1) / 10.0, 0.0, 1.0)

        if X.ndim == 1:
            X = X.reshape(1, -1)

        X_norm = (X - self._mean) / self._std
        tensor_x = torch.tensor(X_norm, dtype=torch.float32).to(self.device)

        self.model.eval()
        with torch.no_grad():
            recon = self.model(tensor_x)
            mse = torch.mean((tensor_x - recon) ** 2, dim=1).cpu().numpy()

        # Sigmoidal mapping centered around normal threshold:
        # score = 1 / (1 + exp(-2 * (mse - threshold) / threshold))
        normalized_error = mse / self._normal_mse_threshold
        # Anomaly score: 0.5 at threshold, approaching 1.0 as error multiplies
        anomaly_scores = 1.0 - np.exp(-0.7 * np.maximum(0.0, normalized_error - 0.5))
        return np.clip(anomaly_scores, 0.0, 1.0)

    def save(self, file_path: str) -> None:
        state = {
            "model_state_dict": self.model.state_dict(),
            "input_dim": self.input_dim,
            "latent_dim": self.latent_dim,
            "mean": self._mean,
            "std": self._std,
            "normal_mse_threshold": self._normal_mse_threshold,
            "version": self.version,
            "is_fitted": self.is_fitted,
        }
        torch.save(state, file_path)

    def load(self, file_path: str) -> "PyTorchAutoencoderDetector":
        state = torch.load(file_path, map_location=self.device)
        self.input_dim = state["input_dim"]
        self.latent_dim = state["latent_dim"]
        self.model = AutoencoderNet(input_dim=self.input_dim, latent_dim=self.latent_dim).to(self.device)
        self.model.load_state_dict(state["model_state_dict"])
        self._mean = state["mean"]
        self._std = state["std"]
        self._normal_mse_threshold = state["normal_mse_threshold"]
        self.version = state["version"]
        self.is_fitted = state["is_fitted"]
        return self

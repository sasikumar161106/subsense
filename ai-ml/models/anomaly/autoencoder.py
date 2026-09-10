"""
1D-Convolutional Autoencoder for multi-sensor strata deformation anomaly detection.
Architecture adheres to Section 5.1:
- Input: 12-dimensional vector (FEATURE_VECTOR_DIM = 12)
- Latent dimension = 4
- LeakyReLU activations
- MSE Loss
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Optional, Tuple
from features.constants import FEATURE_VECTOR_DIM


class Conv1DAutoencoderModel(nn.Module):
    """PyTorch 1D-CNN Autoencoder with latent dimension 4 and LeakyReLU activations."""

    def __init__(self, input_dim: int = FEATURE_VECTOR_DIM, latent_dim: int = 4):
        super().__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim

        # Encoder: 1D convolutions over the 12 feature channels
        self.encoder_conv = nn.Sequential(
            nn.Conv1d(in_channels=1, out_channels=8, kernel_size=3, padding=1),
            nn.LeakyReLU(0.2),
            nn.Conv1d(in_channels=8, out_channels=16, kernel_size=3, padding=1),
            nn.LeakyReLU(0.2),
        )
        self.encoder_fc = nn.Sequential(
            nn.Linear(16 * input_dim, latent_dim),
            nn.LeakyReLU(0.2),
        )

        # Decoder: Project back and reconstruct 12-dimensional vector
        self.decoder_fc = nn.Sequential(
            nn.Linear(latent_dim, 16 * input_dim),
            nn.LeakyReLU(0.2),
        )
        self.decoder_conv = nn.Sequential(
            nn.Conv1d(in_channels=16, out_channels=8, kernel_size=3, padding=1),
            nn.LeakyReLU(0.2),
            nn.Conv1d(in_channels=8, out_channels=1, kernel_size=3, padding=1),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (B, input_dim) -> (B, 1, input_dim)
        x_in = x.unsqueeze(1)
        conv_out = self.encoder_conv(x_in)
        flat = conv_out.view(conv_out.size(0), -1)
        z = self.encoder_fc(flat)
        return z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        # z shape: (B, latent_dim)
        flat = self.decoder_fc(z)
        reshaped = flat.view(flat.size(0), 16, self.input_dim)
        reconstructed = self.decoder_conv(reshaped)
        return reconstructed.squeeze(1)  # (B, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encode(x)
        out = self.decode(z)
        return out


class MineAutoencoder:
    """
    Wrapper handling training, evaluation, MSE computation,
    and per-feature error attribution for the 1D-Conv Autoencoder.
    """

    def __init__(self, latent_dim: int = 4, lr: float = 0.001):
        self.device = torch.device("cpu")
        self.model = Conv1DAutoencoderModel(input_dim=FEATURE_VECTOR_DIM, latent_dim=latent_dim).to(self.device)
        self.criterion = nn.MSELoss(reduction="none")
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.is_fitted = False

    def train_baseline(
        self,
        X_baseline: np.ndarray,
        epochs: int = 40,
        batch_size: int = 32,
    ) -> float:
        """Trains the autoencoder on normal baseline feature vectors."""
        assert X_baseline.shape[1] == FEATURE_VECTOR_DIM
        self.model.train()

        tensor_x = torch.from_numpy(X_baseline.astype(np.float32)).to(self.device)
        dataset = torch.utils.data.TensorDataset(tensor_x)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        final_loss = 0.0
        for epoch in range(epochs):
            total_loss = 0.0
            for (batch,) in loader:
                self.optimizer.zero_grad()
                recon = self.model(batch)
                loss = nn.MSELoss()(recon, batch)
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item() * batch.size(0)
            final_loss = total_loss / len(dataset)

        self.is_fitted = True
        self.model.eval()
        return float(final_loss)

    def evaluate(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Evaluates input vectors.
        Returns:
            overall_mse: (N,) array of mean squared errors across features.
            per_feature_mse: (N, 12) array of squared errors for each feature channel.
        """
        self.model.eval()
        with torch.no_grad():
            is_single = (X.ndim == 1)
            if is_single:
                x_tensor = torch.from_numpy(X.reshape(1, -1).astype(np.float32)).to(self.device)
            else:
                x_tensor = torch.from_numpy(X.astype(np.float32)).to(self.device)

            reconstructed = self.model(x_tensor)
            diff_sq = self.criterion(reconstructed, x_tensor)  # (N, 12)
            overall_mse = torch.mean(diff_sq, dim=1).cpu().numpy()  # (N,)
            per_feature_mse = diff_sq.cpu().numpy()  # (N, 12)

            if is_single:
                return overall_mse[0], per_feature_mse[0]
            return overall_mse, per_feature_mse

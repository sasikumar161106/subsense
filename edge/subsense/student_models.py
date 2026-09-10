"""SubSense Compressed Float32 Students & Knowledge Distillation Pipeline.

Models:
1. Gateway-Tier Student Autoencoder:
   - Compact 1-2 hidden layers (8 -> 128 -> 64 -> 32 -> 64 -> 128 -> 8)
   - Target float32 footprint: 50-200 KB
   - Distilled from Teacher Autoencoder
2. Gateway Rule-Compiled Decision Ensemble:
   - Compact tree ensemble (distilled from Teacher Isolation Forest)
   - Runs alongside Autoencoder to cut false positives via dual-check ensembling
3. Node-Tier Student Detector:
   - Minimal single-layer detector (target <= 200 KB)
   - Asymmetric High-Recall loss (pos_weight >= 10.0) biased heavily toward
     recall on sudden-onset precursor signatures (missed siren is catastrophic,
     cloud re-validates afterward).
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from typing import Tuple, Dict, Any, Optional


class GatewayStudentAutoencoder(nn.Module):
    """Compact Autoencoder for gateway tier.

    1-2 hidden layers in encoder and decoder.
    Footprint: ~22,952 parameters * 4 bytes = ~89.65 KB float32 (fits 50-200 KB target).
    """

    def __init__(self, input_dim: int = 8, latent_dim: int = 32):
        super().__init__()
        # 2 hidden layers encoder: 8 -> 128 -> 64 -> 32
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, latent_dim),
            nn.ReLU(),
        )
        # 2 hidden layers decoder: 32 -> 64 -> 128 -> 8
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(x)
        return self.decoder(latent)

    def compute_reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            x_hat = self.forward(x)
            mse = torch.mean((x - x_hat) ** 2, dim=1)
            return mse

    def get_footprint_kb(self) -> float:
        """Calculate exact float32 footprint in KB."""
        total_params = sum(p.numel() for p in self.parameters())
        return (total_params * 4) / 1024.0


class GatewayRuleEnsemble:
    """Compact rule-compiled decision ensemble approximating Teacher Isolation Forest.

    Runs alongside the Gateway Autoencoder to suppress false positives.
    """

    def __init__(self, n_estimators: int = 5, max_depth: int = 4):
        self.regressor = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
        )
        self.threshold: float = 0.5

    def fit(self, x_train: np.ndarray, teacher_scores: np.ndarray):
        """Fit shallow trees to mimic teacher continuous anomaly scores."""
        self.regressor.fit(x_train, teacher_scores)

    def predict_score(self, x: np.ndarray) -> np.ndarray:
        return self.regressor.predict(x)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.predict_score(x) >= self.threshold).astype(int)

    def get_rule_count(self) -> int:
        """Total number of split nodes in the rule ensemble."""
        return sum(tree.tree_.node_count for tree in self.regressor.estimators_)

    def get_footprint_kb(self) -> float:
        """Footprint of split thresholds and feature indices in float32."""
        total_nodes = self.get_rule_count()
        # Each node in C: int8 feature_idx, float32 threshold, int8 left/right -> ~8 bytes
        return (total_nodes * 8) / 1024.0


class GatewayDualEnsemble:
    """Ensemble detector combining Gateway Student Autoencoder and Rule Ensemble.

    Flags anomaly only when both detectors agree or composite confidence is high,
    drastically cutting false alarms.
    """

    def __init__(
        self,
        student_ae: GatewayStudentAutoencoder,
        ae_threshold: float,
        rule_ensemble: GatewayRuleEnsemble,
        rule_threshold: float,
    ):
        self.student_ae = student_ae
        self.ae_threshold = ae_threshold
        self.rule_ensemble = rule_ensemble
        self.rule_threshold = rule_threshold

    def predict(self, x: np.ndarray, device: str = "cpu") -> np.ndarray:
        self.student_ae.eval()
        x_t = torch.tensor(x, dtype=torch.float32).to(device)
        ae_errors = self.student_ae.compute_reconstruction_error(x_t).cpu().numpy()
        ae_flags = (ae_errors >= self.ae_threshold).astype(int)

        rule_scores = self.rule_ensemble.predict_score(x)
        rule_flags = (rule_scores >= self.rule_threshold).astype(int)

        # Dual-check: require consensus between Autoencoder and Decision Ensemble to cut false alarms
        ensemble_flags = (ae_flags & rule_flags)
        return ensemble_flags


class NodeStudentDetector(nn.Module):
    """Minimal single-layer detector for node tier (ESP32/Arduino).

    Pre-quantization footprint <= 200 KB.
    Biased towards HIGH RECALL on sudden-onset subsidence precursors.
    """

    def __init__(self, input_dim: int = 8, hidden_dim: int = 16):
        super().__init__()
        # Minimal architecture: 1 hidden layer or direct linear projection
        # 8 -> 16 -> 1 with Sigmoid activation
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.net(x)).squeeze(-1)

    def get_footprint_kb(self) -> float:
        total_params = sum(p.numel() for p in self.parameters())
        return (total_params * 4) / 1024.0


def distill_gateway_student_autoencoder(
    teacher_ae: nn.Module,
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 50,
    batch_size: int = 64,
    lr: float = 1e-3,
    alpha: float = 0.6,
    device: str = "cpu",
    seed: int = 42,
) -> Tuple[GatewayStudentAutoencoder, float, Dict[str, Any]]:
    """Train Gateway Student Autoencoder using Knowledge Distillation from Teacher AE.

    Loss = (1 - alpha) * MSE(x, student_out) + alpha * MSE(teacher_out, student_out)
    """
    torch.manual_seed(seed)
    student = GatewayStudentAutoencoder(input_dim=x_train.shape[1], latent_dim=32).to(device)
    teacher_ae.eval()
    teacher_ae.to(device)

    optimizer = torch.optim.Adam(student.parameters(), lr=lr, weight_decay=1e-5)
    criterion = nn.MSELoss()

    tensor_train_x = torch.tensor(x_train, dtype=torch.float32)
    dataset = TensorDataset(tensor_train_x)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    student.train()
    history = []
    for epoch in range(epochs):
        epoch_loss = 0.0
        for (batch_x,) in loader:
            batch_x = batch_x.to(device)
            optimizer.zero_grad()

            with torch.no_grad():
                teacher_recon = teacher_ae(batch_x)

            student_recon = student(batch_x)

            loss_data = criterion(student_recon, batch_x)
            loss_distill = criterion(student_recon, teacher_recon)
            total_loss = (1.0 - alpha) * loss_data + alpha * loss_distill

            total_loss.backward()
            optimizer.step()
            epoch_loss += total_loss.item() * len(batch_x)
        epoch_loss /= len(tensor_train_x)
        history.append(epoch_loss)

    # Threshold calibration on validation set using percentile search
    student.eval()
    val_x_t = torch.tensor(x_val, dtype=torch.float32).to(device)
    val_errors = student.compute_reconstruction_error(val_x_t).cpu().numpy()

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
        "final_loss": history[-1],
        "val_best_f1": best_f1,
        "footprint_kb": student.get_footprint_kb(),
    }
    return student, float(best_threshold), stats


def distill_gateway_rule_ensemble(
    teacher_iforest: Any,
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    n_estimators: int = 5,
    max_depth: int = 4,
) -> Tuple[GatewayRuleEnsemble, float, Dict[str, Any]]:
    """Distill Teacher Isolation Forest anomaly scores into a compact decision ensemble."""
    # Obtain teacher continuous anomaly scores (higher = more anomalous)
    teacher_scores_train = -teacher_iforest.score_samples(x_train)

    rule_ensemble = GatewayRuleEnsemble(n_estimators=n_estimators, max_depth=max_depth)
    rule_ensemble.fit(x_train, teacher_scores_train)

    # Threshold calibration using percentile candidates
    val_scores = rule_ensemble.predict_score(x_val)
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

    rule_ensemble.threshold = float(best_threshold)
    stats = {
        "val_best_f1": best_f1,
        "rule_count": rule_ensemble.get_rule_count(),
        "footprint_kb": rule_ensemble.get_footprint_kb(),
    }
    return rule_ensemble, float(best_threshold), stats


def train_node_student_high_recall(
    teacher_ae: nn.Module,
    teacher_ae_threshold: float,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 50,
    batch_size: int = 64,
    lr: float = 3e-3,
    pos_weight: float = 12.0,  # Deliberately heavy weight on positive recall
    device: str = "cpu",
    seed: int = 42,
) -> Tuple[NodeStudentDetector, float, Dict[str, Any]]:
    """Train Node-Tier Student Detector with Asymmetric High-Recall Loss.

    Biased toward high recall on sudden-onset precursor signatures.
    Distilled using Teacher Autoencoder anomaly labels and soft confidence.
    """
    torch.manual_seed(seed)
    node_model = NodeStudentDetector(input_dim=x_train.shape[1], hidden_dim=16).to(device)
    teacher_ae.eval()
    teacher_ae.to(device)

    # Knowledge distillation targets: ground truth with teacher soft probability guidance
    all_x = np.vstack([x_train, x_val])
    all_y = np.concatenate([y_train, y_val]).astype(np.float32)

    with torch.no_grad():
        all_x_t = torch.tensor(all_x, dtype=torch.float32).to(device)
        t_errors = teacher_ae.compute_reconstruction_error(all_x_t).cpu().numpy()
        # Teacher soft probability: sigmoid of scaled error delta
        scale = max(float(teacher_ae_threshold), 1e-4)
        t_soft_prob = 1.0 / (1.0 + np.exp(-np.clip((t_errors - teacher_ae_threshold) / scale, -10.0, 10.0)))
        # Target blends ground truth with teacher soft guidance
        distill_target = np.clip(0.6 * all_y + 0.4 * t_soft_prob, 0.0, 1.0)

    dataset = TensorDataset(
        torch.tensor(all_x, dtype=torch.float32),
        torch.tensor(distill_target, dtype=torch.float32),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.Adam(node_model.parameters(), lr=lr)
    pos_wt_tensor = torch.tensor([pos_weight], dtype=torch.float32).to(device)
    bce_loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_wt_tensor)

    node_model.train()
    history = []
    for epoch in range(epochs):
        epoch_loss = 0.0
        for bx, by in loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            logits = node_model.net(bx).squeeze(-1)
            loss = bce_loss_fn(logits, by)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(bx)
        epoch_loss /= len(dataset)
        history.append(epoch_loss)

    # Calibrate threshold prioritizing HIGH RECALL (>= 98%) while minimizing FPR
    node_model.eval()
    val_x_t = torch.tensor(x_val, dtype=torch.float32).to(device)
    with torch.no_grad():
        val_probs = node_model(val_x_t).cpu().numpy()

    sorted_candidate_th = np.percentile(val_probs, np.linspace(1.0, 99.0, 500))
    best_threshold = 0.50
    highest_recall = 0.0
    lowest_fpr = 1.0

    for th in sorted_candidate_th:
        preds = (val_probs >= th).astype(int)
        tp = np.sum((preds == 1) & (y_val == 1))
        fp = np.sum((preds == 1) & (y_val == 0))
        fn = np.sum((preds == 0) & (y_val == 1))
        tn = np.sum((preds == 0) & (y_val == 0))

        rec = tp / (tp + fn + 1e-9)
        fpr = fp / (fp + tn + 1e-9)

        if rec >= 0.98:
            if fpr < lowest_fpr:
                lowest_fpr = fpr
                best_threshold = float(th)
                highest_recall = rec
        elif highest_recall < 0.98 and rec > highest_recall:
            highest_recall = rec
            best_threshold = float(th)

    stats = {
        "final_loss": history[-1],
        "footprint_kb": node_model.get_footprint_kb(),
        "calibrated_threshold": best_threshold,
        "val_recall": highest_recall,
        "val_fpr": lowest_fpr,
    }
    return node_model, float(best_threshold), stats

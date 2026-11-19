"""Configuració dels experiments de l'Exercici 7.

Els valors per defecte són el model de l'Exercici 6 amb un early stopping més robust (min_delta i fins
a 40 èpoques, perquè al ej. 6 la F1 encara pujava mil·lèsimes a l'època 30). No s'han de canviar mai: tots
els experiments es defineixen com a variacions sobre ells. La clau de cache només té en compte els camps que
difereixen del valor per defecte, de manera que afegir camps nous no invalida resultats ja calculats.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any


@dataclass
class BlockConfig:
    """Un bloc de l'encoder identificat pel nom amb què s'ha registrat i els seus hiperparàmetres."""

    kind: str
    params: dict[str, Any] = field(default_factory=dict)


def _default_blocks() -> list[BlockConfig]:
    return [BlockConfig("rnn", {"rnn_type": "lstm", "hidden_dim": 128, "num_layers": 1, "bidirectional": True})]


@dataclass
class DataConfig:
    scheme: str = "BILOU"       # "BILOU" o "BIO"
    min_freq: int = 2           # paraules de train menys freqüents van a <unk>
    val_size: int = 900


@dataclass
class ModelConfig:
    embedding_dim: int = 128
    pretrained: str | None = None         # nom dels vectors preentrenats (p. ex. "glove-100"), si n'hi ha
    freeze_embeddings: bool = False
    embedding_dropout: float = 0.0
    char_encoder: BlockConfig | None = None  # representació per caràcters concatenada a la de paraula
    blocks: list[BlockConfig] = field(default_factory=_default_blocks)
    classifier_dropout: float = 0.0
    decoder: str = "softmax"              # "softmax" o qualsevol decodificador registrat (p. ex. "crf")


@dataclass
class TrainConfig:
    batch_size: int = 32
    lr: float = 1e-3
    weight_decay: float = 0.0
    max_epochs: int = 40
    patience: int = 5
    min_delta: float = 1e-3     # millora mínima de F1 de validació per reiniciar la paciència
    grad_clip: float = 1.0
    warmup_epochs: float = 0.0  # warmup lineal del LR, útil sobretot per al Transformer
    class_weighting: str | None = None    # None, "inverse", "inverse_sqrt", "effective"
    effective_beta: float = 0.999         # beta del nombre efectiu de mostres (Cui et al., 2019)
    weight_clip: float | None = None      # límit superior dels pesos (normalitzats a pes mitjà per token 1)
    o_weight: float | None = None         # pes específic per a la classe "O"


@dataclass
class ExperimentConfig:
    name: str = "baseline"      # etiqueta llegible per a taules i gràfics
    section: str = "6"          # apartat de l'enunciat al qual pertany
    seed: int = 0
    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    train: TrainConfig = field(default_factory=TrainConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def key(self) -> str:
        """Hash curt de la configuració efectiva; el nom i l'apartat no hi compten perquè no canvien el model."""
        diff = _non_default(self, ExperimentConfig())
        diff.pop("name", None)
        diff.pop("section", None)
        return hashlib.sha1(json.dumps(diff, sort_keys=True).encode()).hexdigest()[:10]

    def with_(self, name: str | None = None, section: str | None = None, **overrides: Any) -> ExperimentConfig:
        """Còpia amb canvis en notació de punts, p. ex. `cfg.with_(**{"model.embedding_dim": 64})`."""
        new = copy.deepcopy(self)
        for path, value in overrides.items():
            *parents, attr = path.split(".")
            target = new
            for part in parents:
                target = getattr(target, part)
            if not hasattr(target, attr):
                raise AttributeError(f"Camp inexistent a la configuració: {path}")
            setattr(target, attr, value)
        new.name = name if name is not None else new.name
        new.section = section if section is not None else new.section
        return new

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExperimentConfig:
        """Reconstrueix una configuració guardada en un JSON de resultats."""
        model = dict(d["model"])
        model["blocks"] = [BlockConfig(**b) for b in model["blocks"]]
        model["char_encoder"] = BlockConfig(**model["char_encoder"]) if model.get("char_encoder") else None
        known = {f.name for f in fields(ModelConfig)}
        return cls(name=d["name"], section=d["section"], seed=d["seed"],
                   data=_build(DataConfig, d["data"]), model=ModelConfig(**{k: v for k, v in model.items() if k in known}),
                   train=_build(TrainConfig, d["train"]))


def _build(cls: type, values: dict[str, Any]) -> Any:
    """Crea la dataclass ignorant camps antics que ja no existeixen."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in values.items() if k in known})


def _non_default(obj: Any, default: Any) -> dict[str, Any]:
    """Diccionari només amb els camps que difereixen del valor per defecte (recursiu sobre dataclasses)."""
    diff = {}
    for f in fields(obj):
        value, ref = getattr(obj, f.name), getattr(default, f.name)
        if is_dataclass(value) and is_dataclass(ref) and type(value) is type(ref):
            sub = _non_default(value, ref)
            if sub:
                diff[f.name] = sub
        elif value != ref:
            diff[f.name] = asdict(value) if is_dataclass(value) else _plain(value)
    return diff


def _plain(value: Any) -> Any:
    """Converteix llistes de BlockConfig i altres dataclasses a tipus serialitzables en JSON."""
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return asdict(value) if is_dataclass(value) else value


def baseline() -> ExperimentConfig:
    """Configuració de l'Exercici 6: embedding 128, BiLSTM 128, sense dropout ni pesos de classe."""
    return ExperimentConfig()

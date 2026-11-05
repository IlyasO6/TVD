"""Accés al LLM. És l'única part que necessita GPU (torch i transformers s'importen només aquí).

Qualsevol objecte cridable `model(messages, tools, max_new_tokens=None) -> text` serveix com a model: el
xat i l'agent no en depenen, i les proves fan servir un model simulat sense GPU. Amb `tools=None` és una
crida sense tools (la del jutge del guardrail de sortida). Opcionalment, `last_finish` diu si l'última
generació ha acabat sola ('stop') o perquè s'ha arribat al límit de tokens ('length': resposta tallada).
"""

from .config import COMPOSE_TEMPERATURE, COMPOSE_TOP_P, MAX_NEW_TOKENS, MODEL_NAME


class QwenModel:
    """Model de Hugging Face amb plantilla de xat. Es pot crear a partir d'un model i tokenitzador ja
    carregats (al notebook, per no ocupar la T4 dues vegades) o carregar-los pel nom."""

    def __init__(self, model=None, tokenizer=None, name=MODEL_NAME):
        if model is None or tokenizer is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            model = AutoModelForCausalLM.from_pretrained(name, device_map="auto")
            tokenizer = AutoTokenizer.from_pretrained(name)
        self.model, self.tokenizer = model, tokenizer
        self.stop_ids = [tokenizer.convert_tokens_to_ids("<|im_end|>"), tokenizer.eos_token_id]
        self.last_finish = "stop"

    def __call__(self, messages, tools, max_new_tokens=None, sample=False):
        """`sample`: redactar amb mostreig (temperatura moderada) en lloc de la paraula més probable. L'agent el
        fa servir només per redactar la resposta un cop té els resultats de les tools; decidir si cal cercar i
        amb quins arguments continua sent determinista (converses manuals v5: amb greedy, peticions semblants
        rebien literalment la mateixa frase). La llavor surt de l'entrada: la mateixa conversa dona la mateixa
        resposta i les avaluacions són reproduïbles."""
        import hashlib
        text = self.tokenizer.apply_chat_template(messages, tools=tools, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        limit = max_new_tokens or MAX_NEW_TOKENS
        # No s'hi posa repetition_penalty ni no_repeat_ngram_size: a transformers també compten el prompt.
        if sample:
            import torch
            torch.manual_seed(int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16))
            options = {"do_sample": True, "temperature": COMPOSE_TEMPERATURE, "top_p": COMPOSE_TOP_P}
        else:  # greedy (el codi base hi afegia temperature i top_p, que amb do_sample=False no s'apliquen)
            options = {"do_sample": False}
        generated = self.model.generate(**inputs, max_new_tokens=limit, **options,
                                        eos_token_id=self.stop_ids, pad_token_id=self.tokenizer.eos_token_id)
        new_tokens = generated[0][inputs.input_ids.shape[1]:]
        stopped = len(new_tokens) and int(new_tokens[-1]) in self.stop_ids
        self.last_finish = "stop" if stopped or len(new_tokens) < limit else "length"
        # Sense saltar els tokens especials (així es conserva <tool_call>, si el model el fa servir) i
        # traient després només els de final de torn.
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=False)
        return text.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()

    def score(self, messages, options):
        """Probabilitat de cada opció (p.ex. "YES"/"NO") com a primer token de la resposta, renormalitzada
        entre les opcions. Per al jutge: en lloc de generar text, s'obté la confiança del model i es decideix
        amb un llindar calibrable (config.JUDGE_THRESHOLD). Cada opció ha de ser un sol token (amb Qwen,
        "YES" i "NO" ho són; comprovat amb el tokenitzador)."""
        import torch

        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        ids = [self.tokenizer.encode(option, add_special_tokens=False)[0] for option in options]
        with torch.no_grad():
            try:  # només cal l'última posició (si no, ~240 MB de logits per a tot el prompt a la T4)
                logits = self.model(**inputs, logits_to_keep=1).logits[0, -1]
            except TypeError:  # versions de transformers sense logits_to_keep
                logits = self.model(**inputs).logits[0, -1]
        probabilities = torch.softmax(logits[ids].float(), dim=0).tolist()
        return dict(zip(options, probabilities))

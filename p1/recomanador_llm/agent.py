"""Un torn de l'agent: crida el model, executa les tools que demana i retorna la resposta per a l'usuari.

Correccions estructurals respecte a `query_model_with_tools` del notebook base:
- bucle en lloc de recursió, amb un màxim de crides al model per torn (MAX_MODEL_CALLS);
- el JSON invàlid es tracta de veritat (al codi base `json.loads` era fora del `try` i el xat petava);
- es reconeixen els dos formats de crida: el bloc ```json que demana el system prompt i les etiquetes
  <tool_call> que demana la plantilla de Qwen quan se li passen tools;
- una crida repetida es detecta pel nom i els arguments (al codi base, per si el nom de la funció
  apareixia en el missatge anterior) i, en lloc d'un missatge fals de l'usuari, el model rep una
  indicació de sistema;
- les indicacions internes (JSON invàlid, crida repetida, resposta buida) no es desen a l'historial
  de la sessió: només hi queden els missatges reals (usuari, crides, resultats i respostes);
- les crides es desen amb el camp estàndard `tool_calls`, el format que la plantilla de Qwen sap
  representar, en lloc del text en brut.
"""

import json
import re
import time

from . import guardrails, prompts
from .config import LANGUAGE_HINT_POSITION, MAX_MODEL_CALLS, MAX_REGENERATIONS, MAX_TOOL_CALLS
from .tools import TOOLS, run_tool

_BLOCKS = [re.compile(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|$)", re.DOTALL),
           re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)]  # només ```json: un altre bloc de codi no és una crida


def parse_tool_call(text):
    """('none', None) si és una resposta per a l'usuari; ('call', (nom, arguments)) si demana una tool;
    ('invalid', None) si ho intenta però el JSON no és vàlid o no té el format d'una crida."""
    for pattern in _BLOCKS:
        match = pattern.search(text)
        if match:
            payload = match.group(1)
            break
    else:
        # Una crida escrita al mig del text, sense etiquetes ni bloc (bateria v5, F05: "Sure, I'll get the details
        # for #18. {"name": "get_home_details", ...}"): també és una crida, i el client no ha de veure el JSON.
        inline = re.search(r'\{\s*"name"\s*:\s*"(?:search_homes|get_home_details)"', text)
        if not text.lstrip().startswith("{") and not inline:
            return "none", None
        payload = text.strip() if text.lstrip().startswith("{") else text[inline.start():].strip()
        try:
            payload = json.dumps(json.JSONDecoder().raw_decode(payload)[0])  # només l'objecte, sense el que segueix
        except json.JSONDecodeError:
            pass
    try:
        call = json.loads(payload)
        if isinstance(call, dict) and isinstance(call.get("function"), dict):
            call = call["function"]  # {"type": "function", "function": {...}}
        arguments = call.get("arguments", call.get("parameters", {}))
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
    except (json.JSONDecodeError, AttributeError):
        return "invalid", None
    if not isinstance(call.get("name"), str):
        return "invalid", None
    return "call", (call["name"], arguments)


class _Trace:
    """Registre d'un torn (B4). Cada esdeveniment es desa estructurat a `events` (si es dona) i, si té text,
    s'envia a `log` (la sortida verbose del notebook, igual que abans). Es registren tots els intents del model,
    també els rebutjats: sense ells no es pot saber si un guardrail ha encertat (p.ex. si el jutge bloqueja de més)."""

    def __init__(self, log, events):
        self.log, self.events, self.start = log, events, time.perf_counter()

    def __call__(self, kind, message=None, **data):
        if self.events is not None:
            self.events.append({"t": round(time.perf_counter() - self.start, 2), "kind": kind, **data})
        if message and self.log:
            self.log(message)


def _working_copy(history, language):
    """Còpia de treball del torn: l'historial més les indicacions internes, que no es desen.

    La indicació d'idioma va al final del system prompt i no després del missatge del client: a la bateria D,
    amb la indicació com a últim missatge, el model responia a la indicació i no al client (repetia la
    resposta anterior, demanava "l'id de la vivenda" quan l'acabaven de dir i gairebé no cridava les tools).
    Configurable (LANGUAGE_HINT_POSITION) per poder comparar les dues posicions amb la bateria."""
    hint = prompts.LANGUAGE_HINT.format(language=guardrails.LANGUAGE_NAMES[language])
    if LANGUAGE_HINT_POSITION == "after_user":
        return list(history) + [{"role": "system", "content": hint}]
    return [{**history[0], "content": f"{history[0]['content']}\n\n# Language\n{hint}"}] + list(history[1:])


def respond(model, history, user_text, log=None, events=None):
    """Afegeix el torn de l'usuari a `history`, fa treballar el model (amb tools) i retorna la resposta.

    `history` és la llista de missatges de la sessió (comença amb el system prompt) i s'actualitza.
    `log(text)`: si es dona, rep el detall intern (crides a tools i resultats), com el verbose del notebook.
    `events`: si es dona una llista, s'hi afegeix el registre estructurat del torn (B4).
    Guardrails (guardrails.py): d'entrada (un missatge bloquejat té una resposta fixa i no arriba al model
    ni a l'historial), de flux (consultar les tools quan toca), d'execució (arguments ancorats al client i
    validats, màxim per torn, resultats nets) i de sortida (una regeneració si la resposta té un problema;
    després, correccions deterministes o resposta fixa).
    """
    note = _Trace(log, events)
    language = guardrails.turn_language(user_text, history)
    check = guardrails.check_input(user_text, language)
    note("input", f"[input guardrail] blocked: {check.blocked}" if check.blocked else None,
         user=user_text, language=language, blocked=check.blocked)
    if check.blocked:
        answer = guardrails.blocked_reply(check)
        note("answer", text=answer, source="blocked")
        return answer
    history.append({"role": "user", "content": user_text})
    working = _working_copy(history, language)
    executed, tool_calls, regenerations, turn_lines, turn_counts, turn_details = set(), 0, 0, [], set(), set()
    forced = False
    for attempt in range(MAX_MODEL_CALLS):
        start = time.perf_counter()
        # Redactar amb variació només quan ja hi ha resultats de tools en aquest torn (vegeu QwenModel).
        text = model(working, TOOLS, sample=tool_calls > 0)
        truncated = getattr(model, "last_finish", "stop") == "length"
        status, call = parse_tool_call(text)
        note("model", attempt=attempt, output=text, status=status, truncated=truncated,
             seconds=round(time.perf_counter() - start, 2))
        if status == "none" and text.strip():
            # Guardrail de flux: el client ha donat criteris (o un #id) i el model respon sense consultar les
            # tools (a la bateria D: 3 crides en 74 torns). Se li demana una vegada que les cridi.
            action = guardrails.expected_tool(user_text, history) if not tool_calls and not forced else None
            if action:
                forced = True
                nudge = prompts.NUDGE_FORCE_DETAILS if action == "get_home_details" else prompts.NUDGE_FORCE_SEARCH
                note("flow", f"[flow guardrail] answered without {action}: asking to call it", action=action)
                working += [{"role": "assistant", "content": text}, {"role": "system", "content": nudge}]
                continue
            # Guardrail de sortida: primer les regles (barates), després el jutge (una crida curta al model)
            # i finalment l'idioma. Un problema tou (llargada) no evita el jutge: a la bateria, una carta de
            # presentació massa llarga es va acceptar sense que el jutge la veiés (cas R06).
            context = guardrails.output_context(history, language, turn_lines, turn_counts,
                                                guardrails.user_intent(user_text), turn_details)
            problem = guardrails.check_output(text, context, truncated)
            if problem is None or problem.kind in guardrails.SOFT_PROBLEMS:
                problem = guardrails.judge_scope(model, text, note) or problem
            problem = problem or guardrails.check_language(text, context)
            if problem and problem.kind != "leak" and regenerations < MAX_REGENERATIONS:
                regenerations += 1
                note("output", f"[output guardrail] {problem.kind} ({problem.detail}): regenerating",
                     problem=problem.kind, detail=problem.detail, action="regenerate")
                working += [{"role": "assistant", "content": text}, {"role": "system", "content": problem.nudge}]
                continue
            if problem and problem.kind not in guardrails.SOFT_PROBLEMS:
                note("output", f"[output guardrail] {problem.kind} ({problem.detail}): fixed reply",
                     problem=problem.kind, detail=problem.detail, action="fixed")
                answer, source = guardrails.fallback_reply(problem, context), "fixed"
            else:  # sense problemes, o un de tou que persisteix (idioma, llargada...): no és perillós
                if problem:
                    note("output", problem=problem.kind, detail=problem.detail, action="accepted")
                # Una negativa seca que persisteix es substitueix per la resposta del cas: compta com a fixa.
                source = "fixed" if guardrails._is_bare_refusal(text) else "model"
                answer = guardrails.finalize(text, context)
            history.append({"role": "assistant", "content": answer})
            note("answer", text=answer, source=source)
            return answer
        if status != "call":
            nudge = prompts.NUDGE_INVALID_JSON if status == "invalid" else prompts.NUDGE_EMPTY
            note("nudge", f"[nudge] {nudge}", reason=status if status == "invalid" else "empty")
            working += [{"role": "assistant", "content": text}, {"role": "system", "content": nudge}]
            continue
        name, arguments = call
        if name == "search_homes" and isinstance(arguments, dict):
            # Guardrail d'execució: els criteris de la cerca, ancorats al que ha dit el client.
            original = arguments
            arguments, changes = guardrails.ground_search_arguments(arguments, history, user_text)
            if changes:
                note("grounding", f"[execution guardrail] grounded arguments: {'; '.join(changes)}",
                     original=original, grounded=arguments, changes=changes)
        request = {"role": "assistant", "content": "",
                   "tool_calls": [{"type": "function", "function": {"name": name, "arguments": arguments}}]}
        signature = json.dumps([name, arguments], sort_keys=True, default=str)
        if signature in executed:
            note("nudge", f"[nudge] {prompts.NUDGE_REPEATED}", reason="repeated", name=name, arguments=arguments)
            working += [request, {"role": "system", "content": prompts.NUDGE_REPEATED}]
            continue
        executed.add(signature)
        start = time.perf_counter()
        if tool_calls >= MAX_TOOL_CALLS:  # guardrail d'execució: el model ja té prou dades per respondre
            note("execution", f"[execution guardrail] more than {MAX_TOOL_CALLS} tool calls", reason="tool_limit")
            output = f"Error: limit of {MAX_TOOL_CALLS} tool calls per message reached. Answer with the data you have."
        elif name == "get_home_details" and guardrails.ground_details_id(arguments, history):
            # Guardrail d'execució (punt 6): la fitxa d'una vivenda que ningú ha esmentat no s'executa.
            output = guardrails.ground_details_id(arguments, history)
            note("execution", f"[execution guardrail] {output}", reason="id_not_mentioned")
        else:
            tool_calls += 1
            note("tool", f"[tool] {name} {json.dumps(arguments, ensure_ascii=False)}", name=name, arguments=arguments)
            output = run_tool(name, arguments)
            if name == "search_homes" and not output.startswith("Error"):
                turn_lines = [m.group(0) for m in guardrails.HOME_LINE.finditer(output)]
                total = re.search(r"^(\d+) homes? match", output, re.MULTILINE)
                turn_counts |= {len(turn_lines), int(total.group(1)) if total else 0}
            elif name == "get_home_details" and isinstance(arguments, dict) and not output.startswith("Error"):
                turn_details |= {int(n) for n in re.findall(r"\d+", str(arguments.get("id", "")))[:1]}
        note("tool_output", f"[tool output] {output[:300]}{' ...' if len(output) > 300 else ''}", name=name,
             output=output, seconds=round(time.perf_counter() - start, 2))
        result = {"role": "tool", "name": name, "content": output}
        working += [request, result]
        history += [request, result]
    note("execution", f"[limit] {MAX_MODEL_CALLS} model calls", reason="model_limit")
    history.append({"role": "assistant", "content": prompts.GIVE_UP[language]})
    note("answer", text=prompts.GIVE_UP[language], source="give_up")
    return prompts.GIVE_UP[language]

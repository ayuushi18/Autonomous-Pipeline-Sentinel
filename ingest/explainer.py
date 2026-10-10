import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = 'gemini-3.5-flash'


def _renames_text(patch):
    parts = []
    for r in patch['renames']:
        parts.append(r['source'] + ' -> ' + r['target']
                     + ' (confidence ' + str(r['confidence']) + ')')
    return '; '.join(parts)


def template_explanation(decision):
    source = decision['source']
    action = decision['action']

    if action == 'patch_applied':
        return (f"[{source}] The API renamed fields: {_renames_text(decision['patch'])}. "
                "The patch passed every validation check, so it was applied and "
                "downstream code still sees the original field names.")

    if action == 'patch_rejected':
        failed = [name for name, ok in decision['checks'].items() if not ok]
        return (f"[{source}] Possible renames were found "
                f"({_renames_text(decision['patch'])}), but validation failed on: "
                f"{', '.join(failed)}. The data was left unchanged and needs human review.")

    return (f"[{source}] Fields changed (added: {len(decision['added'])}, "
            f"removed: {len(decision['removed'])}) but no confident rename match "
            "was found. No action was taken.")


def llm_explanation(decision):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            'You are explaining an automated data-pipeline decision to a junior '
            'engineer. The decision was already made by deterministic code. Do not '
            'change it or second-guess it. In at most 3 sentences of plain English, '
            'explain what changed, what the system did, and why.\n\n'
            'Decision:\n' + json.dumps(decision, indent=2)
        )
        response = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', DEFAULT_MODEL),
            contents=prompt,
        )
        text = (response.text or '').strip()
        return text or None
    except Exception as e:
        print('LLM explanation failed, using template:', e)
        return None


def explain(decision):
    text = llm_explanation(decision)
    if text:
        return {'text': text, 'by': 'llm'}
    return {'text': template_explanation(decision), 'by': 'template'}
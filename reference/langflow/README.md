# Frozen Langflow reference

`Identifier_LM Studio_Gamma.json` is the previously preserved validated export.
It remains byte-for-byte unchanged for this checkpoint. `SHA256.txt` records:

```text
9cb629b672f9b63dc454be4b9b25fd83032b7be156944894d62363e3216a2006
```

The export identifies Langflow 1.12.2, flow
`88f6a048-d942-421a-af54-d297e8033806`, input `ChatInput-TKjnK`, output
`ChatOutput-KxTA8`, and LM Studio model `google/gemma-4-26b-a4b-qat`.
It includes Agent Instructions, component code and tool settings. It is reference
source, not the Langflow database, uploaded evidence, or login/session state.

The nonsecret `lm-studio` value is the local OpenAI-compatible client's dummy key.
The historical Qwen/Ollama selector remains untouched; actual validated model
calls used the connected LM Studio Gemma component. Do not reinterpret that
editor selector as a requirement to install or switch to Ollama.

See [Windows setup](../../docs/SETUP_WINDOWS.md) for import prerequisites and the
unverified fresh-install ID/authentication boundary. Do not overwrite this export
with a runtime capture containing private images, conversation data or secrets.

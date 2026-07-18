try:
    from langchain_core.tracers.langchain import LangChainTracer
    print("Import succeeded")
    tracer = LangChainTracer()
    print("Tracer created")
except Exception as e:
    print("Error:", e)

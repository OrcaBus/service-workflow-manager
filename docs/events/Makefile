install:
	@pip install -r requirements.txt

schema:
	@python gen_schema.py AnalysisRunStateChange/AnalysisRunStateChange.schema.yaml > AnalysisRunStateChange/AnalysisRunStateChange.schema.json
	@python gen_schema.py AnalysisRunUpdate/AnalysisRunUpdate.schema.yaml > AnalysisRunUpdate/AnalysisRunUpdate.schema.json
	@python gen_schema.py WorkflowRunStateChange/WorkflowRunStateChange.schema.yaml > WorkflowRunStateChange/WorkflowRunStateChange.schema.json
	@python gen_schema.py WorkflowRunUpdate/WorkflowRunUpdate.schema.yaml > WorkflowRunUpdate/WorkflowRunUpdate.schema.json

json:
	@json validate --schema-file=WorkflowRunStateChange/WorkflowRunStateChange.schema.json --document-file=WorkflowRunStateChange/examples/WRSC__example1.json
	@json validate --schema-file=WorkflowRunStateChange/WorkflowRunStateChange.schema.json --document-file=WorkflowRunStateChange/examples/WRSC__example2.json
	@json validate --schema-file=WorkflowRunUpdate/WorkflowRunUpdate.schema.json --document-file=WorkflowRunUpdate/examples/WRU__example1.json
	@json validate --schema-file=WorkflowRunUpdate/WorkflowRunUpdate.schema.json --document-file=WorkflowRunUpdate/examples/WRU__example2.json
	@json validate --schema-file=AnalysisRunStateChange/AnalysisRunStateChange.schema.json --document-file=AnalysisRunStateChange/examples/ARSC__example1.json
	@json validate --schema-file=AnalysisRunStateChange/AnalysisRunStateChange.schema.json --document-file=AnalysisRunStateChange/examples/ARSC__example2.json
	@json validate --schema-file=AnalysisRunUpdate/AnalysisRunUpdate.schema.json --document-file=AnalysisRunUpdate/examples/ARU__example_DRAFT.json
	@json validate --schema-file=AnalysisRunUpdate/AnalysisRunUpdate.schema.json --document-file=AnalysisRunUpdate/examples/ARU__example_READY.json

test:
	@check-jsonschema --schemafile WorkflowRunStateChange/WorkflowRunStateChange.schema.json WorkflowRunStateChange/examples/WRSC__example1.json
	@check-jsonschema --schemafile WorkflowRunStateChange/WorkflowRunStateChange.schema.json WorkflowRunStateChange/examples/WRSC__example2.json
	@check-jsonschema --schemafile WorkflowRunUpdate/WorkflowRunUpdate.schema.json WorkflowRunUpdate/examples/WRU__example1.json
	@check-jsonschema --schemafile WorkflowRunUpdate/WorkflowRunUpdate.schema.json WorkflowRunUpdate/examples/WRU__example2.json
	@check-jsonschema --schemafile AnalysisRunStateChange/AnalysisRunStateChange.schema.json AnalysisRunStateChange/examples/ARSC__example1.json
	@check-jsonschema --schemafile AnalysisRunStateChange/AnalysisRunStateChange.schema.json AnalysisRunStateChange/examples/ARSC__example2.json
	@check-jsonschema --schemafile AnalysisRunUpdate/AnalysisRunUpdate.schema.json AnalysisRunUpdate/examples/ARU__example_DRAFT.json
	@check-jsonschema --schemafile AnalysisRunUpdate/AnalysisRunUpdate.schema.json AnalysisRunUpdate/examples/ARU__example_READY.json

# Event schemas

This is the location of the events defined by the Workflow Manager.
Each event is contained in its own directory and accompanied by examples.

## JSON schema generation

The JSON schema for each event is generated from an annotated YAML file.


Set up Python environment

```bash
# create and activate a virtual env
uv venv  --python 3.12
source .venv/bin/activate
# install dependencies
uv pip install -r requirements.txt
```

Modify the schema YAML file in the corresponding event directory if required.

Run the JSON schema generation script:

```bash
# generate the JSON schema from the annotated YAML file
python gen_schema.py <event name>/<event name>.schemal.yaml > <event name>/<event name>.schema.json
# e.g.:
python gen_schema.py AnalysisRunStateChange/AnalysisRunStateChange.schema.yaml > AnalysisRunStateChange/AnalysisRunStateChange.schema.json
python gen_schema.py AnalysisRunUpdate/AnalysisRunUpdate.schema.yaml > AnalysisRunUpdate/AnalysisRunUpdate.schema.json
python gen_schema.py WorkflowRunStateChange/WorkflowRunStateChange.schema.yaml > WorkflowRunStateChange/WorkflowRunStateChange.schema.json
python gen_schema.py WorkflowRunUpdate/WorkflowRunUpdate.schema.yaml > WorkflowRunUpdate/WorkflowRunUpdate.schema.json
```


## JSON validation

Example events can be validated against their respective JSON schema

```bash
# Example
# If the file is not valid this should produce an exception (non-zero return code)
json validate --schema-file=AnalysisRunUpdate/AnalysisRunUpdate.schema.json --document-file=AnalysisRunUpdate/examples/ARU__example_DRAFT.json
```

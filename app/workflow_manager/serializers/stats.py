from rest_framework import serializers


class WorkflowRunStatusCountSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    aborted = serializers.IntegerField()
    failed = serializers.IntegerField()
    resolved = serializers.IntegerField()
    deprecated = serializers.IntegerField()
    ongoing = serializers.IntegerField()


class AnalysisRunStatusCountSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    aborted = serializers.IntegerField()
    failed = serializers.IntegerField()
    resolved = serializers.IntegerField()
    deprecated = serializers.IntegerField()
    ongoing = serializers.IntegerField()


class WorkflowStatusCountSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    unvalidated = serializers.IntegerField()
    validated = serializers.IntegerField()
    deprecated = serializers.IntegerField()
    failed = serializers.IntegerField()


class AnalysisStatusCountSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()

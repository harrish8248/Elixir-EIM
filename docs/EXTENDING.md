# Elixir EIM - Plugin Development Guide (< 1 Hour)

## 1. Extension Points Overview
Elixir EIM provides clean provider interfaces and event-driven hooks:
- **`StorageProvider`**: Custom blob storage backends (S3, Azure Blob, Google Cloud Storage).
- **`SearchProvider`**: Custom search engines (Postgres FTS, OpenSearch, Elasticsearch).
- **`WorkflowNodeHandler`**: Custom workflow tasks and integrations.
- **`VirusScanner`**: Custom antimalware scanning services.
- **`RenditionEngine`**: Custom document transformation and watermarking pipelines.

## 2. Anatomy of a Plugin
Every plugin must reside in `apps/api/app/extensions/plugins/<plugin_name>` or an external directory, and contain:
```
my_plugin/
├── plugin.yaml          # Plugin metadata, version, and hook declarations
├── __init__.py
└── handlers.py          # Implementation of provider or event listeners
```

## 3. Example: Building a Watermark Stamper in 30 Minutes
See the reference plugin at `apps/api/app/extensions/plugins/watermark_stamper`.
It hooks into `content.rendition_generated` and applies classification markings to PDF renditions.

class ProjectionEnvelope {
  const ProjectionEnvelope({
    required this.projection,
    required this.schemaVersion,
    required this.data,
    this.generatedAt,
  });

  final String projection;
  final int schemaVersion;
  final Map<String, dynamic> data;
  final DateTime? generatedAt;

  static ProjectionEnvelope parse(Map<String, dynamic> json) {
    final meta = json['meta'];
    final data = json['data'];
    if (meta is! Map<String, dynamic> || data is! Map<String, dynamic>) {
      throw const FormatException('Invalid projection envelope');
    }
    final version = meta['schema_version'];
    if (version != 1) {
      throw FormatException('Unsupported schema_version: $version');
    }
    return ProjectionEnvelope(
      projection: meta['projection']?.toString() ?? '',
      schemaVersion: version as int,
      data: data,
      generatedAt: DateTime.tryParse(meta['generated_at']?.toString() ?? ''),
    );
  }
}

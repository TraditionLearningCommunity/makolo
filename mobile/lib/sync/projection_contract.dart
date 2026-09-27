import 'projection_meta_dto.dart';

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

    final parsedMeta = ProjectionMetaDto.fromJson(meta);
    if (parsedMeta.schemaVersion != 1) {
      throw FormatException(
        'Unsupported schema_version: ${parsedMeta.schemaVersion}',
      );
    }

    return ProjectionEnvelope(
      projection: parsedMeta.projection,
      schemaVersion: parsedMeta.schemaVersion,
      data: data,
      generatedAt: parsedMeta.generatedAt,
    );
  }
}

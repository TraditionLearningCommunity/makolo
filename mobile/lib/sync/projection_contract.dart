import 'projection_meta_dto.dart';

/// Transport framing for server-owned projection facts.
class ProjectionEnvelope {
  const ProjectionEnvelope({
    required this.projection,
    required this.schemaVersion,
    required this.data,
    this.generatedAt,
    this.scope,
    this.meta = const {},
  });

  final String projection;
  final int schemaVersion;
  final Map<String, dynamic> data;
  final DateTime? generatedAt;
  final String? scope;
  final Map<String, dynamic> meta;

  static ProjectionEnvelope parse(
    Map<String, dynamic> json, {
    String? expectedProjection,
    String? expectedScope,
  }) {
    final rawMeta = json['meta'];
    final rawData = json['data'];
    if (rawMeta is! Map<String, dynamic> ||
        rawData is! Map<String, dynamic>) {
      throw const FormatException('Invalid projection envelope');
    }

    final parsedMeta = ProjectionMetaDto.fromJson(rawMeta);
    if (parsedMeta.schemaVersion != 1) {
      throw FormatException(
        'Unsupported schema_version: ${parsedMeta.schemaVersion}',
      );
    }
    if (parsedMeta.projection.trim().isEmpty ||
        (expectedProjection != null &&
            parsedMeta.projection != expectedProjection)) {
      throw FormatException(
        'Unexpected projection: ${parsedMeta.projection}',
      );
    }
    final scope = rawMeta['scope'];
    if (expectedScope != null &&
        (scope is! String || scope != expectedScope)) {
      throw const FormatException('Unexpected projection scope');
    }
    if (scope != null && (scope is! String || scope.trim().isEmpty)) {
      throw const FormatException('Invalid projection scope');
    }

    return ProjectionEnvelope(
      projection: parsedMeta.projection,
      schemaVersion: parsedMeta.schemaVersion,
      data: rawData,
      generatedAt: parsedMeta.generatedAt,
      scope: scope as String?,
      meta: Map.unmodifiable(rawMeta),
    );
  }
}

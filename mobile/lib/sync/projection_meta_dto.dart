import 'package:json_annotation/json_annotation.dart';

part 'projection_meta_dto.g.dart';

@JsonSerializable(createToJson: false)
class ProjectionMetaDto {
  const ProjectionMetaDto({
    required this.projection,
    required this.schemaVersion,
    this.generatedAt,
  });

  final String projection;

  @JsonKey(name: 'schema_version')
  final int schemaVersion;

  @JsonKey(name: 'generated_at')
  final DateTime? generatedAt;

  factory ProjectionMetaDto.fromJson(Map<String, dynamic> json) =>
      _$ProjectionMetaDtoFromJson(json);
}

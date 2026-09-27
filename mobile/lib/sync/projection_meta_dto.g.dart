// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'projection_meta_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ProjectionMetaDto _$ProjectionMetaDtoFromJson(Map<String, dynamic> json) =>
    ProjectionMetaDto(
      projection: json['projection'] as String,
      schemaVersion: (json['schema_version'] as num).toInt(),
      generatedAt: json['generated_at'] == null
          ? null
          : DateTime.parse(json['generated_at'] as String),
    );

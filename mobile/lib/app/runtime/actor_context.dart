enum ActorContextKind { personal, space }

sealed class ActorContext {
  const ActorContext();

  ActorContextKind get kind;
}

final class PersonalActorContext extends ActorContext {
  const PersonalActorContext();

  @override
  ActorContextKind get kind => ActorContextKind.personal;

  @override
  bool operator ==(Object other) => other is PersonalActorContext;

  @override
  int get hashCode => ActorContextKind.personal.hashCode;
}

final class SpaceActorIdentity {
  SpaceActorIdentity({required String id, required String slug})
    : id = _required(id, 'id'),
      slug = _required(slug, 'slug');

  final String id;
  final String slug;

  static String _required(String value, String field) {
    final normalized = value.trim();
    if (normalized.isEmpty) {
      throw ArgumentError.value(value, field, 'must not be empty');
    }
    return normalized;
  }

  @override
  bool operator ==(Object other) =>
      other is SpaceActorIdentity && other.id == id && other.slug == slug;

  @override
  int get hashCode => Object.hash(id, slug);
}

final class ActorPerspective {
  const ActorPerspective.all() : id = null;

  ActorPerspective.opaque(String value) : id = _normalize(value);

  final String? id;

  bool get isAll => id == null;

  static String _normalize(String value) {
    final normalized = value.trim();
    if (normalized.isEmpty) {
      throw ArgumentError.value(value, 'value', 'must not be empty');
    }
    return normalized;
  }

  @override
  bool operator ==(Object other) => other is ActorPerspective && other.id == id;

  @override
  int get hashCode => id.hashCode;
}

final class SpaceActorContext extends ActorContext {
  SpaceActorContext({
    required this.space,
    this.perspective = const ActorPerspective.all(),
  });

  final SpaceActorIdentity space;
  final ActorPerspective perspective;

  @override
  ActorContextKind get kind => ActorContextKind.space;

  SpaceActorContext copyWith({ActorPerspective? perspective}) {
    return SpaceActorContext(
      space: space,
      perspective: perspective ?? this.perspective,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is SpaceActorContext &&
      other.space == space &&
      other.perspective == perspective;

  @override
  int get hashCode => Object.hash(space, perspective);
}

final class ActorContextCodec {
  const ActorContextCodec._();

  static const int schemaVersion = 1;

  static Map<String, dynamic> encode(ActorContext context) {
    return switch (context) {
      PersonalActorContext() => const {
        'version': schemaVersion,
        'kind': 'personal',
      },
      SpaceActorContext(:final space, :final perspective) => {
        'version': schemaVersion,
        'kind': 'space',
        'space': {'id': space.id, 'slug': space.slug},
        'perspective': perspective.isAll
            ? const {'kind': 'all'}
            : {'kind': 'opaque', 'id': perspective.id},
      },
    };
  }

  static ActorContext? decode(Object? value) {
    if (value is! Map) return null;

    final json = <String, dynamic>{};
    for (final entry in value.entries) {
      if (entry.key is! String) return null;
      json[entry.key as String] = entry.value;
    }

    if (json['version'] != schemaVersion) return null;

    switch (json['kind']) {
      case 'personal':
        return const PersonalActorContext();
      case 'space':
        return _decodeSpace(json);
      default:
        return null;
    }
  }

  static ActorContext? _decodeSpace(Map<String, dynamic> json) {
    final rawSpace = json['space'];
    final rawPerspective = json['perspective'];
    if (rawSpace is! Map || rawPerspective is! Map) return null;

    final id = rawSpace['id'];
    final slug = rawSpace['slug'];
    if (id is! String || slug is! String) return null;

    SpaceActorIdentity space;
    try {
      space = SpaceActorIdentity(id: id, slug: slug);
    } on ArgumentError {
      return null;
    }

    final perspectiveKind = rawPerspective['kind'];
    if (perspectiveKind == 'all') {
      return SpaceActorContext(space: space);
    }
    if (perspectiveKind != 'opaque') return null;

    final perspectiveId = rawPerspective['id'];
    if (perspectiveId is! String) return null;

    try {
      return SpaceActorContext(
        space: space,
        perspective: ActorPerspective.opaque(perspectiveId),
      );
    } on ArgumentError {
      return null;
    }
  }
}

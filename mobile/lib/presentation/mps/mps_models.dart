import '../../data/local/profile_store.dart';

const mpsArtifactProjectionKind = 'mps.artifact';
const mpsTemplateProjectionKind = 'mps.template.version';
const mpsThemeProjectionKind = 'mps.theme.version';

const mpsEssentialTemplateResourceKey = 'builtin:makolo-essential:1';
const mpsEssentialThemeResourceKey = 'builtin:makolo-essential-theme:1';

const Map<String, dynamic> mpsEssentialManifest = {
  'schema_version': 1,
  'purposes': [
    'public_page',
    'invitation',
    'access_pass',
    'confirmation',
    'program',
    'badge',
  ],
  'surfaces': ['web', 'print'],
  'layout': {
    'component': 'Page',
    'props': {'surface': 'web'},
    'children': [
      {'component': 'MakoloMark', 'props': <String, dynamic>{}},
      {
        'component': 'Heading',
        'props': {
          'value': {'binding': 'activity.display_title'},
          'level': 1,
        },
      },
      {'component': 'OccurrenceDetails', 'props': <String, dynamic>{}},
      {
        'component': 'Text',
        'props': {
          'value': {'binding': 'editorial.intro'},
        },
      },
      {'component': 'AccessSummary', 'props': <String, dynamic>{}},
      {
        'component': 'QRCode',
        'props': {'alt': 'QR d’accès Makolo'},
      },
      {
        'component': 'Footer',
        'props': {
          'value': {'binding': 'editorial.footer_note'},
        },
      },
    ],
  },
};

const Map<String, dynamic> mpsEssentialTheme = {
  'background': '#FAF7F5',
  'surface': '#FFFFFF',
  'text': '#0F172A',
  'muted': '#475569',
  'accent': '#5232DB',
  'font_family': 'system',
  'radius': 'md',
  'density': 'normal',
  'border_style': 'solid',
  'motion': 'none',
};

class MpsDefinitionRef {
  const MpsDefinitionRef({
    required this.resourceKey,
    required this.builtin,
    this.path,
  });

  final String resourceKey;
  final bool builtin;
  final String? path;

  factory MpsDefinitionRef.fromJson(Object? value) {
    final map = mpsMap(value);
    final resourceKey = mpsString(map['resource_key']);
    if (resourceKey == null) {
      throw const FormatException('Missing MPS definition resource_key.');
    }
    return MpsDefinitionRef(
      resourceKey: resourceKey,
      builtin: map['builtin'] == true,
      path: mpsString(map['path']),
    );
  }
}

class MpsArtifact {
  const MpsArtifact({
    required this.resourceKey,
    required this.purpose,
    required this.template,
    required this.theme,
    required this.context,
    required this.capabilities,
    required this.links,
    required this.rendererContract,
    required this.minimumRendererVersion,
  });

  final String resourceKey;
  final String purpose;
  final MpsDefinitionRef template;
  final MpsDefinitionRef theme;
  final Map<String, dynamic> context;
  final Set<String> capabilities;
  final Map<String, String> links;
  final String rendererContract;
  final int minimumRendererVersion;

  bool get canOpenCredential =>
      capabilities.contains('open_credential') &&
      links.containsKey('credential');

  factory MpsArtifact.fromProjection(StoredProjection projection) {
    if (projection.kind != mpsArtifactProjectionKind) {
      throw FormatException('Expected $mpsArtifactProjectionKind.');
    }
    final payload = projection.payload;
    final identity = mpsMap(payload['identity']);
    final renderer = mpsMap(payload['renderer']);
    final resourceKey = mpsString(identity['resource_key']);
    final purpose = mpsString(payload['purpose']);
    final contract = mpsString(renderer['contract']);
    final minimum = renderer['minimum_renderer_version'];
    if (resourceKey == null ||
        purpose == null ||
        contract != 'mps.native.v1' ||
        minimum is! int) {
      throw const FormatException('Invalid MPS artifact contract.');
    }
    return MpsArtifact(
      resourceKey: resourceKey,
      purpose: purpose,
      template: MpsDefinitionRef.fromJson(payload['template']),
      theme: MpsDefinitionRef.fromJson(payload['theme']),
      context: mpsMap(payload['context']),
      capabilities: mpsStrings(payload['capabilities']).toSet(),
      links: mpsStringMap(payload['links']),
      rendererContract: contract!,
      minimumRendererVersion: minimum,
    );
  }
}

class MpsPresentationPackage {
  const MpsPresentationPackage({
    required this.artifact,
    required this.manifest,
    required this.themeTokens,
    required this.usedFallback,
  });

  final MpsArtifact artifact;
  final Map<String, dynamic> manifest;
  final Map<String, dynamic> themeTokens;
  final bool usedFallback;
}

Map<String, dynamic> mpsMap(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

List<String> mpsStrings(Object? value) {
  if (value is! List) return const [];
  return value.map((item) => item.toString()).toList(growable: false);
}

Map<String, String> mpsStringMap(Object? value) {
  final source = mpsMap(value);
  return {
    for (final entry in source.entries)
      if (mpsString(entry.value) != null) entry.key: mpsString(entry.value)!,
  };
}

String? mpsString(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

import 'dart:async';
import 'dart:io';

import '../../platform/files/passport_pdf_saver.dart';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../data/files/profile_paths.dart';

import '../../platform/sharing/share_gateway.dart';

import 'package:flutter/services.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';
import '../../sync/projection_contract.dart';
import '../../repositories/personal_repository.dart';
import 'me_local_preview.dart';
import 'me_passport_visibility_screen.dart';

/// Native presentation of the same server-owned Passport variants as Web.
class MePassportScreen extends StatefulWidget {
  const MePassportScreen({
    super.key,
    required this.api,
    this.personal,
    this.onEdit,
  });
  final MakoloApiClient api;
  final PersonalRepository? personal;
  final Future<void> Function()? onEdit;
  @override
  State<MePassportScreen> createState() => _MePassportScreenState();
}

class _MePassportScreenState extends State<MePassportScreen> {
  String _variant = 'complete';
  String? _topic;
  final Set<String> _sections = {};
  final Set<String> _activities = {}, _proofs = {}, _credentials = {};
  Map<String, dynamic>? _full;
  bool _exporting = false;
  bool _onlineReady = false;
  int _loadEpoch = 0;
  Map<String, dynamic>? _cachedPassport;
  String? _cachedVariantKey;
  Uint8List? _cachedAvatar;
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _restorePassport();
    _future = _load();
  }

  @override
  void didUpdateWidget(covariant MePassportScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.personal?.store.profileId !=
            widget.personal?.store.profileId ||
        oldWidget.api != widget.api) {
      ++_loadEpoch;
      _variant = 'complete';
      _topic = null;
      _full = null;
      _cachedAvatar = null;
      _cachedPassport = null;
      _cachedVariantKey = null;
      _onlineReady = false;
      _restorePassport();
      _future = _load();
    }
  }

  String _passportStorageKey() {
    final params = _passportParams();
    // The selection is part of the document identity: no cross-variant reuse.
    final ordered = params.keys.toList()..sort();
    return ordered
        .map((key) {
          final value = params[key];
          if (value is List) {
            final sorted = value.map((v) => v.toString()).toList()..sort();
            return '$key=${sorted.join(",")}';
          }
          return '$key=$value';
        })
        .join('&');
  }

  Future<void> _restorePassport() async {
    try {
      final avatar = await _avatarFile();
      if (avatar != null && await avatar.exists() && mounted) {
        setState(() => _cachedAvatar = avatar.readAsBytesSync());
      }
    } on Object {
      // The photo cannot block the owner's Passport projection.
    }
  }

  Future<File?> _avatarFile() async {
    final id = widget.personal?.store.profileId;
    if (id == null || id.isEmpty) return null;
    final root = await ProfilePaths.privateRoot(id);
    return File('${root.path}/passport-avatar.jpg');
  }

  Future<void> _persistAvatar(Map<String, dynamic> data) async {
    final avatar = _text(_map(data['identity'])['avatar_url']);
    final local = await _avatarFile();
    if (local == null) return;
    if (avatar == null) {
      // A disclosure-limited public/thematic/custom Passport can omit the
      // portrait without deleting the owner's private offline image.
      if (data['variant'] != 'complete') return;
      if (await local.exists()) await local.delete();
      if (mounted) setState(() => _cachedAvatar = null);
      return;
    }
    final uri = Uri.tryParse(avatar);
    if (uri == null) return;
    final base = widget.api.baseUri;
    if ((uri.hasAuthority || uri.hasScheme) &&
        (uri.host != base.host ||
            uri.scheme != base.scheme ||
            uri.port != base.port)) {
      return;
    }
    final path = uri.hasAuthority
        ? uri.replace(scheme: '', host: '', port: null).toString()
        : avatar;
    if (!path.startsWith('/') || path.startsWith('//')) return;
    try {
      final bytes = await widget.api.getPresentationImage(path);
      if (bytes.length > 2 * 1024 * 1024) return;
      await local.parent.create(recursive: true);
      await local.writeAsBytes(bytes, flush: true);
      if (mounted) setState(() => _cachedAvatar = bytes);
    } on Object {
      // Retain the previously authorized portrait while offline.
    }
  }

  static const _sourceKey = 'variant=complete';

  bool get _hasLocalComposition =>
      _full != null && _map(_full!['composition'])['schema_version'] == 1;

  Map<String, dynamic> _composePassport(
    Map<String, dynamic> complete, {
    String? variant,
  }) {
    final requested = variant ?? _variant;
    final composition = _map(complete['composition']);
    if (requested == 'complete' || composition['schema_version'] != 1) {
      return complete;
    }
    final allowed = _map(composition['public_ids']);
    List<Map<String, dynamic>> publicRows(Object? value, String family) {
      final ids = (allowed[family] is List ? allowed[family] as List : const [])
          .map((id) => id.toString())
          .toSet();
      return _rows(value)
          .where((row) => ids.contains(row['id']?.toString()))
          .toList();
    }

    bool inTopic(Map<String, dynamic> row, {bool declaration = false}) {
      if (requested != 'thematic') return true;
      if (_topic == null) return false;
      if (declaration) {
        return _map(row['topic'])['code'] == _topic;
      }
      final codes = row['topic_codes'];
      return codes is List && codes.any((code) => code == _topic);
    }

    List<Map<String, dynamic>> filtered(
      Object? rows,
      String family, {
      bool declaration = false,
      Set<String>? excluded,
    }) {
      return publicRows(rows, family).where((row) {
        if (!inTopic(row, declaration: declaration)) return false;
        if (requested == 'custom' &&
            excluded != null &&
            excluded.contains(row['id']?.toString())) {
          return false;
        }
        return true;
      }).toList();
    }

    final declared = _map(complete['declared']);
    final established = _map(complete['established']);
    final issued = _map(complete['issued']);
    final identity = Map<String, dynamic>.from(
      _map(composition['public_identity']),
    );
    if (requested == 'custom') {
      for (final entry in <String, String>{
        'avatar': 'avatar_url',
        'bio': 'bio',
        'profession': 'profession',
        'company_name': 'company_name',
        'organization_name': 'organization_name',
        'location': 'location',
      }.entries) {
        if (_sections.contains(entry.key)) identity[entry.value] = '';
      }
      if (_sections.contains('links')) identity['links'] = const [];
      if (_sections.contains('profession')) {
        // The hero headline is the same professional fact as profession.
        identity['headline'] = '';
      }
      if (_sections.contains('location')) {
        // Coordinates admitted to Public may also appear in the personal
        // details grid, independently of the hero location label.
        final details = Map<String, dynamic>.from(
          _map(identity['presentation_details']),
        );
        details.remove('city');
        details.remove('country');
        identity['presentation_details'] = details;
      }
    }
    return {
      ...complete,
      'variant': requested,
      'identity': identity,
      'personal_details': _map(identity['presentation_details']),
      'private_details': <String, dynamic>{},
      'collectives': <String, dynamic>{},
      'declared': {
        ...declared,
        'interests': requested == 'custom' && _sections.contains('interests')
            ? <Map<String, dynamic>>[]
            : filtered(declared['interests'], 'interests', declaration: true),
        'open_to': requested == 'custom' && _sections.contains('open_to')
            ? <Map<String, dynamic>>[]
            : filtered(declared['open_to'], 'open_to', declaration: true),
      },
      'activities': filtered(
        complete['activities'],
        'activities',
        excluded: _activities,
      ),
      'experiences':
          requested == 'custom' && _sections.contains('activity_involvements')
          ? <Map<String, dynamic>>[]
          : filtered(complete['experiences'], 'experiences'),
      'established': {
        ...established,
        'proofs': filtered(established['proofs'], 'proofs', excluded: _proofs),
      },
      'issued': {
        ...issued,
        'credentials': filtered(
          issued['credentials'],
          'credentials',
          excluded: _credentials,
        ),
      },
      'projection': {..._map(complete['projection']), 'variant': requested},
    };
  }

  Map<String, dynamic> _passportParams() {
    final params = <String, dynamic>{'variant': _variant};
    if (_variant == 'thematic' && _topic != null) params['topic'] = _topic;
    if (_variant == 'custom') {
      // Send only what was removed from the public baseline. The server
      // validates every requested exclusion against owned, admitted facts.
      params['exclude'] = _sections.toList();
      params['exclude_activity'] = _activities.toList();
      params['exclude_proof'] = _proofs.toList();
      params['exclude_credential'] = _credentials.toList();
    }
    return params;
  }

  /// A root projection can supply a genuinely known, partial owner Passport
  /// even before the dedicated protected Passport depth has been received.
  /// It is not stored as a complete server-issued Passport.
  Future<Map<String, dynamic>?> _rootPassportPreview() async {
    if (widget.personal == null || _variant != 'complete') return null;
    final root = MeLocalPreview.forProfile(
      await widget.personal!.store.readProjection('personal.me'),
      widget.personal!.store.profileId,
    );
    final identity = root?.identity;
    if (identity == null) return null;
    final name = _text(identity['display_name']) ?? _text(identity['username']);
    if (name == null) return null;
    final place = _map(identity['location']);
    final location = [
      _text(place['city']),
      _text(place['country']),
    ].whereType<String>().join(', ');
    return <String, dynamic>{
      'variant': 'complete',
      'identity': {
        'name': name,
        'username': identity['username'],
        'avatar_url': identity['avatar_url'],
        'profession': identity['profession'],
        'bio': identity['bio'],
        'location': location,
        'links': const [],
      },
      'declared': {
        'interests':
            root?.collection('considerations', 'interests')?['items'] ??
            const [],
        'open_to':
            root?.collection('considerations', 'open_to')?['items'] ?? const [],
      },
      'activities': const [],
      'established': {'proofs': const []},
      'issued': {'credentials': const []},
    };
  }

  Future<Map<String, dynamic>> _load({bool preferLocal = true}) async {
    final epoch = ++_loadEpoch;
    final requestedVariant = _variant;
    final resourceKey = _passportStorageKey();

    void keep(Map<String, dynamic> data, {bool online = false}) {
      if (!mounted ||
          epoch != _loadEpoch ||
          resourceKey != _passportStorageKey()) {
        return;
      }
      setState(() {
        _cachedPassport = data;
        _cachedVariantKey = resourceKey;
        if (online) _onlineReady = true;
      });
    }

    if (preferLocal && _hasLocalComposition) {
      final result = _composePassport(_full!, variant: requestedVariant);
      keep(result);
      return result;
    }

    if (preferLocal && widget.personal != null) {
      try {
        final stored = await widget.personal!.store.readProjection(
          'personal.me.passport',
          resourceKey: _sourceKey,
        );
        final source = stored?.payload;
        if (source != null &&
            source['variant'] == 'complete' &&
            _map(source['composition'])['schema_version'] == 1 &&
            epoch == _loadEpoch &&
            resourceKey == _passportStorageKey()) {
          _full = source;
          _onlineReady = false;
          final result = _composePassport(source, variant: requestedVariant);
          keep(result);
          unawaited(
            _load(preferLocal: false)
                .then((fresh) {
                  if (mounted &&
                      requestedVariant == _variant &&
                      resourceKey == _passportStorageKey()) {
                    setState(() => _future = Future.value(fresh));
                  }
                })
                .catchError((Object _) {}),
          );
          return result;
        }
      } on Object {
        // The owner cache is replaceable; a missing copy never grants access.
      }
    }

    try {
      final response = await widget.api.get(
        'api/v1/me/passport/?variant=complete',
      );
      final complete = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport',
      ).data;
      if (complete['variant'] != 'complete') {
        throw const FormatException('Incomplete Passport source');
      }
      if (epoch != _loadEpoch ||
          requestedVariant != _variant ||
          resourceKey != _passportStorageKey()) {
        throw const FormatException('Obsolete Passport response');
      }
      final modern = _map(complete['composition'])['schema_version'] == 1;
      Map<String, dynamic> result = complete;
      if (modern) {
        result = _composePassport(complete, variant: requestedVariant);
      } else if (requestedVariant != 'complete') {
        // Tolerate a backend not yet exposing the owner composition contract.
        final legacyResponse = await widget.api.get(
          Uri(
            path: 'api/v1/me/passport/',
            queryParameters: _passportParams(),
          ).toString(),
        );
        result = ProjectionEnvelope.parse(
          legacyResponse.jsonObject(),
          expectedProjection: 'personal.me.passport',
        ).data;
      }
      if (epoch != _loadEpoch ||
          requestedVariant != _variant ||
          resourceKey != _passportStorageKey()) {
        throw const FormatException('Obsolete Passport selection');
      }
      _full = complete;
      if (widget.personal != null && modern) {
        try {
          await widget.personal!.store.putProjection(
            kind: 'personal.me.passport',
            resourceKey: _sourceKey,
            schemaVersion: 1,
            payload: complete,
          );
        } on Object {
          // A local persistence error must not discard authoritative facts.
        }
      }
      keep(result, online: true);
      unawaited(_persistAvatar(complete));
      return result;
    } on Object catch (error) {
      if (epoch != _loadEpoch ||
          requestedVariant != _variant ||
          resourceKey != _passportStorageKey()) {
        rethrow;
      }
      if (error is MakoloApiError &&
          (error.statusCode == 403 || error.statusCode == 404)) {
        _full = null;
        if (widget.personal != null) {
          try {
            await widget.personal!.store.deleteProjection(
              'personal.me.passport',
              resourceKey: _sourceKey,
            );
          } on Object {
            // Refusal always clears the active projection despite local I/O.
          }
        }
        if (mounted) {
          setState(() {
            _cachedPassport = null;
            _cachedVariantKey = null;
            _onlineReady = false;
          });
        }
        rethrow;
      }
      if (_hasLocalComposition) {
        _onlineReady = false;
        return _composePassport(_full!, variant: requestedVariant);
      }
      if (requestedVariant == 'complete') {
        final preview = await _rootPassportPreview();
        if (preview != null) {
          _onlineReady = false;
          keep(preview);
          return preview;
        }
      }
      rethrow;
    }
  }

  static Map<String, dynamic> _map(Object? raw) => raw is Map
      ? raw.map((key, value) => MapEntry(key.toString(), value))
      : <String, dynamic>{};
  static List<Map<String, dynamic>> _rows(Object? raw) =>
      raw is List ? raw.whereType<Map>().map(_map).toList() : const [];
  static String? _text(Object? raw) =>
      raw is String && raw.trim().isNotEmpty ? raw.trim() : null;

  void _select(String variant) {
    if (_variant == variant) return;
    if (variant == 'thematic' && _topic == null) {
      final options = _rows(_full?['topic_options']);
      if (options.isNotEmpty) _topic = options.first['code']?.toString();
    }
    if (_hasLocalComposition) ++_loadEpoch;
    setState(() {
      _variant = variant;
      if (_hasLocalComposition) {
        final result = _composePassport(_full!);
        _cachedPassport = result;
        _cachedVariantKey = _passportStorageKey();
        _future = Future.value(result);
      } else {
        _onlineReady = false;
        _cachedPassport = null;
        _cachedVariantKey = null;
        _future = _load();
      }
    });
  }

  static String _historicalDate(Object? raw) {
    final value = raw?.toString();
    if (value == null) return '';
    final parsed = DateTime.tryParse(value);
    if (parsed == null) return value;
    final date = parsed.toLocal();
    String two(int x) => x.toString().padLeft(2, '0');
    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)}';
  }

  Future<void> _openDatedVersion(
    String snapshotId, {
    List<Map<String, dynamic>> activeShares = const [],
  }) async {
    try {
      final response = await widget.api.get(
        'api/v1/me/passport/history/$snapshotId/',
      );
      final version = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.version',
      ).data;
      if (!mounted) return;
      final payload = _map(version['payload']);
      final identity = _map(payload['identity']);
      final rows = _rows(payload['activities']);
      final proofs = _rows(payload['proofs']);
      final credentials = _rows(payload['credentials']);
      final readOnly = <String, dynamic>{
        'variant': version['variant'],
        'identity': {
          ...identity,
          'avatar_url': '',
          'links': [
            for (final link
                in identity['links'] is List
                    ? identity['links'] as List
                    : const [])
              if (link is List && link.length >= 2)
                {'label': link[0], 'url': link[1]},
          ],
        },
        'personal_details': version['variant'] == 'complete'
            ? <String, dynamic>{}
            : _map(identity['presentation_details']),
        'private_details': version['variant'] == 'complete'
            ? _map(identity['owner_details'])
            : <String, dynamic>{},
        'declared': {
          'interests': [
            for (final item
                in payload['interests'] is List
                    ? payload['interests'] as List
                    : const [])
              {
                'topic': {'label': item.toString()},
              },
          ],
          'open_to': [
            for (final item in _rows(payload['open_to']))
              {
                'label': [
                  if (_text(item['kind']) != null) item['kind'],
                  if (_text(item['topic']) != null) item['topic'],
                ].join(' · '),
              },
          ],
        },
        'activities': [
          for (final row in rows) {...row, 'status_label': row['status']},
        ],
        'experiences': _rows(payload['activity_involvements']),
        'established': {
          'proofs': [
            for (final row in proofs)
              {
                'proof_type_label': row['label'],
                'activity': {'title': row['activity']},
              },
          ],
        },
        'issued': {
          'credentials': [
            for (final row in credentials)
              {
                ...row,
                'issuer': {'name': row['issuer']},
                'status_label': row['status'],
              },
          ],
        },
        'collectives': {
          'team_affiliations': payload['team_affiliations'],
          'active_space_mandates': payload['active_space_mandates'],
        },
      };
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (context) => SafeArea(
          child: FractionallySizedBox(
            heightFactor: 0.85,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 32),
              children: [
                Text(
                  'Version du ${_historicalDate(version['generated_at'])}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 5),
                Text(
                  version['document_id']?.toString() ?? '',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (version['revoked'] == true)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      'Version révoquée · archive personnelle uniquement',
                    ),
                  ),
                if (activeShares.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  for (final grant in activeShares)
                    if (grant['id'] != null)
                      ListTile(
                        dense: true,
                        leading: const Icon(Icons.link_off_outlined),
                        title: const Text('Révoquer un lien de partage'),
                        subtitle: Text(_historicalDate(grant['expires_at'])),
                        onTap: () {
                          Navigator.pop(context);
                          _revokeDatedShare(grant['id'].toString());
                        },
                      ),
                ],
                const SizedBox(height: 16),
                _PassportBody(data: readOnly, baseUri: widget.api.baseUri),
              ],
            ),
          ),
        ),
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cette version datée n’est pas disponible.'),
        ),
      );
    }
  }

  Future<void> _shareDatedVersion(String snapshotId) async {
    var selectedDays = 7;
    final days = await showDialog<int>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, updateDialog) => AlertDialog(
          title: const Text('Partager cette version émise ?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<int>(
                initialValue: selectedDays,
                decoration: const InputDecoration(
                  labelText: 'Durée du partage',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 1, child: Text('1 jour')),
                  DropdownMenuItem(value: 7, child: Text('7 jours')),
                  DropdownMenuItem(value: 30, child: Text('30 jours')),
                ],
                onChanged: (value) {
                  if (value != null) {
                    updateDialog(() => selectedDays = value);
                  }
                },
              ),
            ],
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              onPressed: () => Navigator.pop(dialogContext),
              appearance: MakoloActionAppearance.quiet,
            ),
            MakoloActionButton(
              label: 'Créer le lien',
              onPressed: () => Navigator.pop(dialogContext, selectedDays),
              appearance: MakoloActionAppearance.primary,
            ),
          ],
        ),
      ),
    );
    if (days == null || !mounted) return;
    try {
      final response = await widget.api.post(
        'api/v1/me/passport/history/$snapshotId/share/',
        body: {'days': days},
      );
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.share',
      ).data;
      final url = _text(data['share_url']);
      if (url == null) throw const FormatException('Missing sharing link');
      await const SystemShareGateway().shareText(url);
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Partage de cette version indisponible.')),
      );
    }
  }

  Future<void> _revokeDatedVersion(String snapshotId) async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Révoquer cette version ?'),
        content: const Text(
          'La version restera dans votre historique, mais tous ses liens '
          'actifs et sa lecture publique seront retirés. Les PDF déjà '
          'enregistrés par un destinataire ne peuvent pas être rappelés.',
        ),
        actions: [
          MakoloActionButton(
            label: 'Conserver',
            onPressed: () => Navigator.pop(dialogContext, false),
            appearance: MakoloActionAppearance.quiet,
          ),
          MakoloActionButton(
            label: 'Révoquer la version',
            onPressed: () => Navigator.pop(dialogContext, true),
            appearance: MakoloActionAppearance.danger,
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    try {
      final response = await widget.api.post(
        'api/v1/me/passport/history/$snapshotId/revoke/',
        body: const {},
      );
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.version',
      ).data;
      if (data['revoked'] != true) {
        throw const FormatException('Version revocation not confirmed');
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Version et partages révoqués.')),
      );
      await _showDatedHistory();
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Révocation de la version impossible.')),
      );
    }
  }

  Future<void> _revokeDatedShare(String shareId) async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Révoquer ce lien ?'),
        content: const Text(
          'Ce lien cessera de fonctionner. Le document émis et les autres '
          'liens éventuels restent inchangés.',
        ),
        actions: [
          MakoloActionButton(
            label: 'Conserver',
            onPressed: () => Navigator.pop(dialogContext, false),
            appearance: MakoloActionAppearance.quiet,
          ),
          MakoloActionButton(
            label: 'Révoquer le lien',
            onPressed: () => Navigator.pop(dialogContext, true),
            appearance: MakoloActionAppearance.danger,
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    try {
      final response = await widget.api.post(
        'api/v1/me/passport/shares/$shareId/revoke/',
        body: const {},
      );
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.share',
      ).data;
      if (data['revoked'] != true) {
        throw const FormatException('Share revocation not confirmed');
      }
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Lien de partage révoqué.')));
      await _showDatedHistory();
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Révocation du lien impossible.')),
      );
    }
  }

  Future<void> _saveDatedVersionPdf(
    String snapshotId,
    String documentId,
  ) async {
    if (_exporting) return;
    setState(() => _exporting = true);
    String? stagingPath;
    try {
      final profileId = widget.personal?.store.profileId;
      if (profileId == null) throw StateError('Profil requis.');
      final directory = await ProfilePaths.reconstructibleCache(profileId);
      stagingPath = '${directory.path}/passeport-makolo-$snapshotId.pdf';
      await widget.api.download(
        'api/v1/me/passport/history/$snapshotId/pdf/',
        destinationPath: stagingPath,
      );
      final saved = await savePassportPdf(
        stagingPath,
        'passeport-makolo-$documentId.pdf',
      );
      if (saved != null && mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('PDF enregistré.')));
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Téléchargement indisponible.')),
        );
      }
    } finally {
      if (stagingPath != null) await _discardTemporaryPdf(stagingPath);
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _showDatedHistory() async {
    try {
      final response = await widget.api.get('api/v1/me/passport/history/');
      final history = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.history',
      ).data;
      if (!mounted) return;
      final entries = _rows(history['items']);
      var hasMore = history['has_more'] == true;
      var nextOffset = history['next_offset'] is int
          ? history['next_offset'] as int
          : entries.length;
      var loading = false;

      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheetContext) => StatefulBuilder(
          builder: (sheetContext, updateSheet) => SafeArea(
            child: FractionallySizedBox(
              heightFactor: 0.75,
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(18, 8, 18, 12),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Versions datées',
                        style: Theme.of(sheetContext).textTheme.titleLarge,
                      ),
                    ),
                  ),
                  Expanded(
                    child: entries.isEmpty
                        ? const Center(child: Text('Aucune version émise.'))
                        : ListView.builder(
                            itemCount: entries.length,
                            itemBuilder: (context, index) {
                              final row = entries[index];
                              final revoked = row['revoked'] == true;
                              final intact = row['integrity_ok'] == true;
                              return ListTile(
                                leading: Icon(
                                  revoked
                                      ? Icons.history_toggle_off
                                      : Icons.history_outlined,
                                ),
                                title: Text(
                                  row['document_id']?.toString() ?? '',
                                ),
                                subtitle: Text(
                                  '${_historicalDate(row['generated_at'])} · '
                                  '${row['variant'] ?? ''}'
                                  '${revoked ? ' · Révoqué' : ''}'
                                  '${!intact ? ' · Non intègre' : ''}',
                                ),
                                onTap: !intact || row['id'] == null
                                    ? null
                                    : () {
                                        final id = row['id'].toString();
                                        Navigator.pop(sheetContext);
                                        _openDatedVersion(
                                          id,
                                          activeShares: _rows(
                                            row['active_shares'],
                                          ),
                                        );
                                      },
                                trailing: row['id'] != null && intact
                                    ? Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          IconButton(
                                            tooltip:
                                                'Télécharger cette version',
                                            icon: const Icon(
                                              Icons.picture_as_pdf_outlined,
                                            ),
                                            onPressed: () {
                                              final id = row['id'].toString();
                                              Navigator.pop(sheetContext);
                                              _saveDatedVersionPdf(
                                                id,
                                                row['document_id']
                                                        ?.toString() ??
                                                    id,
                                              );
                                            },
                                          ),
                                          IconButton(
                                            tooltip: 'Partager cette version',
                                            icon: const Icon(
                                              Icons.share_outlined,
                                            ),
                                            onPressed:
                                                revoked ||
                                                    row['variant'] == 'complete'
                                                ? null
                                                : () {
                                                    final id = row['id']
                                                        .toString();
                                                    Navigator.pop(sheetContext);
                                                    _shareDatedVersion(id);
                                                  },
                                          ),
                                          IconButton(
                                            tooltip: 'Révoquer cette version',
                                            icon: const Icon(
                                              Icons.block_outlined,
                                            ),
                                            onPressed: revoked
                                                ? null
                                                : () {
                                                    final id = row['id']
                                                        .toString();
                                                    Navigator.pop(sheetContext);
                                                    _revokeDatedVersion(id);
                                                  },
                                          ),
                                        ],
                                      )
                                    : null,
                              );
                            },
                          ),
                  ),
                  if (hasMore)
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: TextButton(
                        onPressed: loading
                            ? null
                            : () async {
                                updateSheet(() => loading = true);
                                try {
                                  final page = await widget.api.get(
                                    'api/v1/me/passport/history/?offset=$nextOffset',
                                  );
                                  final data = ProjectionEnvelope.parse(
                                    page.jsonObject(),
                                    expectedProjection:
                                        'personal.me.passport.history',
                                  ).data;
                                  if (!sheetContext.mounted) return;
                                  updateSheet(() {
                                    entries.addAll(_rows(data['items']));
                                    hasMore = data['has_more'] == true;
                                    nextOffset = data['next_offset'] is int
                                        ? data['next_offset'] as int
                                        : entries.length;
                                  });
                                } on Object {
                                  if (!sheetContext.mounted) return;
                                  ScaffoldMessenger.of(
                                    sheetContext,
                                  ).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        'Chargement des versions indisponible.',
                                      ),
                                    ),
                                  );
                                } finally {
                                  if (sheetContext.mounted) {
                                    updateSheet(() => loading = false);
                                  }
                                }
                              },
                        child: Text(
                          loading ? 'Chargement…' : 'Voir plus de versions',
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Historique indisponible. Vérifiez la connexion et vos droits.',
          ),
        ),
      );
    }
  }

  Future<String?> _downloadPassport() async {
    if (_exporting) return null;
    setState(() => _exporting = true);
    try {
      final profileId = widget.personal?.store.profileId;
      if (profileId == null || profileId.trim().isEmpty) {
        throw StateError('Profil requis pour conserver le PDF temporaire.');
      }
      final directory = await ProfilePaths.reconstructibleCache(profileId);
      final file = '${directory.path}/passeport-makolo-$_variant.pdf';
      final url = Uri(
        path: 'api/v1/me/passport/pdf/',
        queryParameters: _passportParams(),
      ).toString();
      final response = await widget.api.download(url, destinationPath: file);
      final disposition =
          response.headers.entries
              .where(
                (entry) => entry.key.toLowerCase() == 'content-disposition',
              )
              .map((entry) => entry.value)
              .firstOrNull ??
          '';
      final suggestedName = RegExp(r'filename="?([A-Za-z0-9._-]+\.pdf)"?')
          .firstMatch(disposition)
          ?.group(1);
      if (suggestedName != null &&
          suggestedName.startsWith('passeport-makolo-')) {
        final datedFile = '${directory.path}/$suggestedName';
        if (datedFile != file) {
          await File(file).rename(datedFile);
          return datedFile;
        }
      }
      return file;
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Exportation du Passeport indisponible.'),
          ),
        );
      }
      if (mounted) setState(() => _exporting = false);
      return null;
    }
  }

  Future<void> _discardTemporaryPdf(String path) async {
    try {
      final file = File(path);
      if (await file.exists()) await file.delete();
    } on Object {
      // No cached export is a source of Passport authority.
    }
  }

  Future<void> _exportPdf() async {
    if (_exporting || !_onlineReady) return;
    final file = await _downloadPassport();
    if (file == null) return;
    try {
      final saved = await savePassportPdf(
        file,
        file.split(Platform.pathSeparator).last,
      );
      if (mounted && saved != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Passeport PDF enregistré.')),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enregistrement impossible.')),
        );
      }
    } finally {
      await _discardTemporaryPdf(file);
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<String?> _issueCurrentVersion({bool shareable = false}) async {
    if (!_onlineReady || _exporting) return null;
    setState(() => _exporting = true);
    try {
      final params = shareable && _variant == 'complete'
          ? <String, dynamic>{'variant': 'public'}
          : _passportParams();
      final url = Uri(
        path: 'api/v1/me/passport/issue/',
        queryParameters: params,
      ).toString();
      final response = await widget.api.post(url, body: const {});
      final issued = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.issuance',
      ).data;
      final id = _text(issued['id']);
      if (id == null) throw const FormatException('Issued document missing id');
      return id;
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Émission indisponible. Vérifiez votre connexion et la sélection.',
            ),
          ),
        );
      }
      return null;
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<String?> _createShareUrl(String snapshotId) async {
    final response = await widget.api.post(
      'api/v1/me/passport/history/$snapshotId/share/',
      body: const {'days': 7},
    );
    final data = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'personal.me.passport.share',
    ).data;
    return _text(data['share_url']);
  }

  Future<void> _copyCurrentPassportLink() async {
    final snapshotId = await _issueCurrentVersion(shareable: true);
    if (snapshotId == null || !mounted) return;
    try {
      final link = await _createShareUrl(snapshotId);
      if (link == null) throw const FormatException('No dated share URL');
      await Clipboard.setData(ClipboardData(text: link));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Lien du Passeport copié.')),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Lien indisponible.')));
      }
    }
  }

  Future<void> _shareInMakolo() async {
    final query = TextEditingController();
    final recipient = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheet) => _PassportRecipientPicker(
        api: widget.api,
        query: query,
        onSelected: (row) => Navigator.pop(sheet, row),
      ),
    );
    query.dispose();
    if (recipient == null || !mounted) return;
    final id = _text(recipient['id']);
    if (id == null) return;
    final snapshotId = await _issueCurrentVersion(shareable: true);
    if (snapshotId == null || !mounted) return;
    try {
      final response = await widget.api.post(
        'api/v1/me/passport/history/$snapshotId/deliver/',
        body: {'recipient_id': id},
      );
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.passport.delivery',
      ).data;
      if (data['state'] != 'delivered') {
        throw const FormatException('Delivery not confirmed');
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Passeport partagé dans Makolo.')),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Partage Makolo indisponible.')),
        );
      }
    }
  }

  Future<void> _sharePassport(Map<String, dynamic> data) async {
    final publicPath = _text(_map(data['links'])['public_web']);
    final canShareLink =
        _map(data['projection'])['public_profile_enabled'] == true &&
        publicPath != null &&
        publicPath.startsWith('/') &&
        !publicPath.startsWith('//');
    final action = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.picture_as_pdf_outlined),
              title: const Text('Partager le PDF'),
              onTap: () => Navigator.pop(sheet, 'pdf'),
            ),
            ListTile(
              leading: const Icon(Icons.people_outline),
              title: const Text('Partager dans Makolo'),
              onTap: () => Navigator.pop(sheet, 'makolo'),
            ),
            ListTile(
              leading: const Icon(Icons.link_outlined),
              title: const Text('Partager le lien public'),
              enabled: canShareLink,
              onTap: () => Navigator.pop(sheet, 'public'),
            ),
            ListTile(
              leading: const Icon(Icons.copy_outlined),
              title: const Text('Copier le lien du Passeport'),
              onTap: () => Navigator.pop(sheet, 'copy_dated'),
            ),
          ],
        ),
      ),
    );
    if (action == null || !mounted) return;
    if (action == 'pdf') {
      final file = await _downloadPassport();
      if (file == null) return;
      try {
        await const SystemShareGateway().shareFiles(paths: [file]);
      } finally {
        await _discardTemporaryPdf(file);
        if (mounted) setState(() => _exporting = false);
      }
      return;
    }
    if (action == 'makolo') {
      await _shareInMakolo();
      return;
    }
    if (action == 'copy_dated') {
      await _copyCurrentPassportLink();
      return;
    }
    if (action == 'public' && canShareLink) {
      final url = widget.api.baseUri.resolve(publicPath).toString();
      await Clipboard.setData(ClipboardData(text: url));
      await const SystemShareGateway().shareText(url);
    }
  }

  Future<void> _shareCurrentPassport() async {
    // Revalidate disclosure with the server before offering sharing actions.
    setState(() => _onlineReady = false);
    try {
      final data = await _load(preferLocal: false);
      if (!mounted || !_onlineReady) return;
      await _sharePassport(data);
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Partage indisponible. Vérifiez la connexion et vos droits.',
          ),
        ),
      );
    }
  }

  Future<void> _editAndRefresh() async {
    final openEditor = widget.onEdit;
    if (openEditor == null) return;
    await openEditor();
    if (!mounted) return;
    ++_loadEpoch;
    setState(() {
      _full = null;
      _cachedPassport = null;
      _cachedVariantKey = null;
      _onlineReady = false;
      _future = _load(preferLocal: false);
    });
  }

  Future<void> _configureVisibility() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => MePassportVisibilityScreen(api: widget.api),
      ),
    );
    if (!mounted) return;
    setState(() {
      _onlineReady = false;
      _cachedPassport = null;
      _cachedVariantKey = null;
      _full = null;
      _future = _load(preferLocal: false);
    });
  }

  void _toggle(Set<String> values, String id, bool excluded) {
    if (_hasLocalComposition) ++_loadEpoch;
    setState(() {
      if (excluded) {
        values.add(id);
      } else {
        values.remove(id);
      }
      if (_hasLocalComposition) {
        final result = _composePassport(_full!);
        _cachedPassport = result;
        _cachedVariantKey = _passportStorageKey();
        _future = Future.value(result);
      } else {
        _onlineReady = false;
        _future = _load();
      }
    });
  }

  Widget _options(Map<String, dynamic> data) {
    final source = _variant == 'custom' && _hasLocalComposition
        ? _composePassport(_full!, variant: 'public')
        : _full ?? data;
    final topics = _rows(source['topic_options']);
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final option in const [
                ('complete', 'Complet'),
                ('public', 'Public'),
                ('thematic', 'Thématique'),
                ('custom', 'Personnalisé'),
              ])
                Padding(
                  padding: const EdgeInsets.only(right: 7),
                  child: ChoiceChip(
                    label: Text(option.$2),
                    selected: _variant == option.$1,
                    onSelected: (_) => _select(option.$1),
                  ),
                ),
            ],
          ),
        ),
        if (_variant == 'thematic') ...[
          const SizedBox(height: 10),
          if (topics.isNotEmpty)
            DropdownButtonFormField<String>(
              initialValue: _topic,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Thème',
                border: OutlineInputBorder(),
              ),
              items: [
                for (final topic in topics)
                  if (topic['code'] != null)
                    DropdownMenuItem(
                      value: topic['code'].toString(),
                      child: Text(topic['label']?.toString() ?? ''),
                    ),
              ],
              onChanged: (code) {
                if (_hasLocalComposition) ++_loadEpoch;
                setState(() {
                  _topic = code;
                  if (_hasLocalComposition) {
                    final result = _composePassport(_full!);
                    _cachedPassport = result;
                    _cachedVariantKey = _passportStorageKey();
                    _future = Future.value(result);
                  } else {
                    _onlineReady = false;
                    _future = _load();
                  }
                });
              },
            ),
        ],
        if (_variant == 'custom') ...[
          const SizedBox(height: 14),
          Text('À présenter', style: theme.textTheme.titleMedium),
          Wrap(
            spacing: 6,
            children: [
              for (final option in const [
                ('avatar', 'Photo'),
                ('bio', 'À propos'),
                ('profession', 'Profession'),
                ('company_name', 'Entreprise renseignée'),
                ('organization_name', 'Organisation renseignée'),
                ('location', 'Localisation'),
                ('links', 'Liens'),
                ('interests', 'Intérêts'),
                ('open_to', 'Ouvert à'),
                ('activity_involvements', 'Expériences'),
              ])
                FilterChip(
                  label: Text(option.$2),
                  selected: !_sections.contains(option.$1),
                  onSelected: (v) => _toggle(_sections, option.$1, !v),
                ),
            ],
          ),
          _selection(
            'Activités',
            _rows(source['activities']),
            _activities,
            (row) => _text(row['title']),
          ),
          _selection(
            'Faits établis',
            _rows(_map(source['established'])['proofs']),
            _proofs,
            (row) => _text(row['proof_type_label']),
          ),
          _selection(
            'Attestations',
            _rows(_map(source['issued'])['credentials']),
            _credentials,
            (row) => _text(row['title']),
          ),
        ],
      ],
    );
  }

  Widget _selection(
    String heading,
    List<Map<String, dynamic>> rows,
    Set<String> selected,
    String? Function(Map<String, dynamic>) label,
  ) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 10),
        Text(heading, style: Theme.of(context).textTheme.labelLarge),
        for (final row in rows)
          if (row['id'] != null && label(row) != null)
            CheckboxListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(label(row)!),
              value: !selected.contains(row['id'].toString()),
              onChanged: (enabled) =>
                  _toggle(selected, row['id'].toString(), enabled != true),
            ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Passeport'),
      actions: [
        MakoloIconActionButton(
          tooltip: 'Confidentialité',
          onPressed: _configureVisibility,
          icon: Icons.shield_outlined,
        ),
        MakoloIconActionButton(
          tooltip: 'Versions datées',
          onPressed: _onlineReady ? _showDatedHistory : null,
          icon: Icons.history_outlined,
        ),
        MakoloIconActionButton(
          tooltip: 'PDF',
          onPressed: _exporting || !_onlineReady ? null : _exportPdf,
          icon: Icons.picture_as_pdf_outlined,
        ),
        MakoloIconActionButton(
          tooltip: 'Partager le Passeport',
          onPressed: _exporting || !_onlineReady ? null : _shareCurrentPassport,
          icon: Icons.share_outlined,
        ),
      ],
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      key: ValueKey(_passportStorageKey()),
      future: _future,
      builder: (context, snapshot) {
        // FutureBuilder may retain the previous variant while a new request
        // is pending. Never show that data as if it were the new variant.
        final stored = _cachedVariantKey == _passportStorageKey()
            ? _cachedPassport
            : null;
        final futureData = snapshot.data;
        final exact = futureData != null && futureData['variant'] == _variant
            ? futureData
            : null;
        if (stored == null && exact == null) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              _options(const <String, dynamic>{}),
              const SizedBox(height: 30),
              const Icon(Icons.cloud_off_outlined, size: 40),
              const SizedBox(height: 12),
              Text(
                snapshot.hasError
                    ? 'Passeport indisponible. Vos informations ne sont pas modifiées.'
                    : 'Aucun contenu à présenter dans cette sélection.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Center(
                child: MakoloActionButton(
                  label: 'Réessayer',
                  onPressed: () => setState(() {
                    _onlineReady = false;
                    _future = _load(preferLocal: false);
                  }),
                  appearance: MakoloActionAppearance.secondary,
                ),
              ),
            ],
          );
        }
        final data = stored ?? exact!;
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            _options(data),
            const SizedBox(height: 16),
            _PassportBody(
              data: data,
              baseUri: widget.api.baseUri,
              cachedAvatar: _cachedAvatar,
            ),
            if (widget.onEdit != null)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: MakoloActionButton(
                  label: 'Modifier le Passeport',
                  onPressed: _editAndRefresh,
                  icon: Icons.edit_outlined,
                  appearance: MakoloActionAppearance.secondary,
                ),
              ),
          ],
        );
      },
    ),
  );
}

class _PassportBody extends StatelessWidget {
  const _PassportBody({
    required this.data,
    required this.baseUri,
    this.cachedAvatar,
  });
  final Map<String, dynamic> data;
  final Uri baseUri;
  final Uint8List? cachedAvatar;

  static Map<String, dynamic> _map(Object? raw) => raw is Map
      ? raw.map((key, item) => MapEntry(key.toString(), item))
      : <String, dynamic>{};
  static String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
  static List<Map<String, dynamic>> _rows(Object? value) =>
      value is List ? value.whereType<Map>().map(_map).toList() : const [];

  @override
  Widget build(BuildContext context) {
    final identity = _map(data['identity']);
    final declared = _map(data['declared']);
    final established = _map(data['established']);
    final issued = _map(data['issued']);
    final collectives = _map(data['collectives']);
    final name =
        _text(identity['display_name']) ??
        _text(identity['name']) ??
        _text(identity['username']) ??
        'Mon passeport';
    final bio = _text(identity['bio']);
    final profession = _text(identity['profession']);
    final companyName = _text(identity['company_name']);
    final organizationName = _text(identity['organization_name']);
    final location = _text(identity['location']);
    final links = _rows(identity['links']);
    // Owner-only data and publicly admissible personal facts never share
    // a disclosure container. The same section renders the admitted subset.
    final personalDetails = data['variant'] == 'complete'
        ? _map(data['private_details'])
        : data['personal_details'] != null
        ? _map(data['personal_details'])
        : _map(identity['presentation_details']);
    final missing = <String>[
      if (bio == null) 'À propos',
      if (profession == null) 'Profession',
      if (location == null) 'Localisation',
      if (links.isEmpty) 'Liens',
      if (_rows(declared['interests']).isEmpty) 'Centres d’intérêt',
      if (_rows(declared['open_to']).isEmpty) 'Ouvert à',
      if (_rows(data['experiences']).isEmpty) 'Expériences',
      if (_rows(data['activities']).isEmpty) 'Activités portées',
      if (_rows(established['proofs']).isEmpty) 'Faits établis',
      if (_rows(issued['credentials']).isEmpty) 'Attestations reçues',
    ];
    final avatar = _text(identity['avatar_url']);
    final avatarUri = avatar == null
        ? null
        : (avatar.startsWith('/') && !avatar.startsWith('//')
              ? baseUri.resolve(avatar)
              : Uri.tryParse(avatar));
    final safeAvatar =
        avatarUri != null &&
        (avatarUri.scheme == 'https' || avatarUri.scheme == 'http') &&
        avatarUri.host == baseUri.host;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [MakoloColors.indigo, MakoloColors.deep],
            ),
            borderRadius: BorderRadius.circular(MakoloRadii.large),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (cachedAvatar != null && avatar != null)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.memory(
                        cachedAvatar!,
                        width: 54,
                        height: 54,
                        fit: BoxFit.cover,
                      ),
                    )
                  else if (safeAvatar)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.network(
                        avatarUri.toString(),
                        width: 54,
                        height: 54,
                        fit: BoxFit.cover,
                        errorBuilder: (_, _, _) => const Icon(
                          Icons.badge_outlined,
                          color: Colors.white,
                          size: 42,
                        ),
                      ),
                    )
                  else
                    const Icon(
                      Icons.badge_outlined,
                      color: Colors.white,
                      size: 42,
                    ),
                  const Spacer(),
                  Text(
                    'MAKOLO',
                    style: Theme.of(context).textTheme.labelMedium
                        ?.copyWith(color: Colors.white70, letterSpacing: 2),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                name,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (profession != null)
                Text(
                  profession,
                  style: Theme.of(context).textTheme.bodyMedium
                      ?.copyWith(color: Colors.white70),
                ),
              if (location != null)
                Text(
                  location,
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(color: Colors.white70),
                ),
            ],
          ),
        ),
        if (companyName != null || organizationName != null)
          Padding(
            padding: const EdgeInsets.only(top: 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (companyName != null)
                  Text('Entreprise renseignée · $companyName'),
                if (organizationName != null)
                  Text('Organisation renseignée · $organizationName'),
              ],
            ),
          ),
        if (personalDetails.isNotEmpty)
          _personalDetails(context, personalDetails),
        if (bio != null)
          Padding(
            padding: const EdgeInsets.only(top: 18),
            child: Text(bio, style: Theme.of(context).textTheme.bodyLarge),
          ),
        if (links.isNotEmpty) ...[
          const SizedBox(height: 18),
          Text(
            'Liens',
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          for (final link in links)
            if (_text(link['label']) != null && _text(link['url']) != null)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(link['label'].toString()),
                subtitle: SelectableText(link['url'].toString()),
              ),
        ],
        _section(
          context,
          'Centres d’intérêt',
          _rows(declared['interests']),
          (row) => _text(_map(row['topic'])['label']),
        ),
        _section(context, 'Ouvert à', _rows(declared['open_to']), (row) {
          final label = _text(row['label']);
          final topic = _text(_map(row['topic'])['label']);
          return label == null ? null : [label, ?topic].join(' · ');
        }),
        _section(context, 'Expériences et rôles', _rows(data['experiences']), (
          row,
        ) {
          final title = _text(row['title']);
          if (title == null) return null;
          return [
            title,
            if (_text(row['role']) != null) _text(row['role'])!,
            if (_text(row['date']) != null) _text(row['date'])!,
          ].join(' · ');
        }),
        _section(context, 'Activités portées', _rows(data['activities']), (
          row,
        ) {
          final title = _text(row['title']);
          final status = _text(row['status_label']);
          return title == null ? null : [title, ?status].join(' · ');
        }),
        _section(context, 'Faits établis', _rows(established['proofs']), (row) {
          final type = _text(row['proof_type_label']);
          final activity = _text(_map(row['activity'])['title']);
          return type == null ? null : [type, ?activity].join(' · ');
        }),
        _section(context, 'Attestations reçues', _rows(issued['credentials']), (
          row,
        ) {
          final title = _text(row['title']);
          final issuer = _map(row['issuer']);
          final issuerName =
              _text(issuer['name']) ?? _text(issuer['display_name']);
          final status = _text(row['status_label']);
          return title == null
              ? null
              : [
                  title,
                  if (issuerName != null) 'Délivrée par $issuerName',
                  ?status,
                ].join(' · ');
        }),
        _section(
          context,
          'Équipes et Espaces',
          _rows(collectives['team_affiliations']),
          (row) {
            final team = _text(row['team']);
            final space = _text(row['space']);
            return team == null ? null : [team, ?space].join(' · ');
          },
        ),
        _section(
          context,
          'Mes groupes',
          _rows(collectives['group_affiliations']),
          (row) => _text(row['name']),
        ),
        _section(
          context,
          'Espaces accessibles',
          _rows(collectives['authorized_space_affiliations']),
          (row) => _text(row['name']),
        ),
        _section(
          context,
          'Mandats actifs',
          _rows(collectives['active_space_mandates']),
          (row) {
            final role = _text(row['role']);
            final space = _text(row['space']);
            return role == null ? null : [role, ?space].join(' · ');
          },
        ),
        if (data['variant'] == 'complete' && missing.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 20),
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('À enrichir'),
              subtitle: Text('${missing.length} rubriques'),
              children: [
                for (final label in missing)
                  ListTile(dense: true, title: Text(label)),
              ],
            ),
          ),
      ],
    );
  }

  Widget _personalDetails(BuildContext context, Map<String, dynamic> details) {
    const fields = <(String, String)>[
      ('first_name', 'Prénom'),
      ('last_name', 'Nom'),
      ('username', 'Identifiant Makolo'),
      ('city', 'Ville'),
      ('country', 'Pays'),
      ('phone', 'Téléphone'),
      ('address', 'Adresse'),
      ('birth_date', 'Date de naissance'),
      ('gender', 'Genre'),
    ];
    final visible = [
      for (final field in fields)
        if (_text(details[field.$1]) != null) field,
    ];
    if (visible.isEmpty) return const SizedBox.shrink();
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.person_outline_rounded,
                color: colors.primary,
                size: 21,
              ),
              const SizedBox(width: 9),
              Text(
                'Informations personnelles',
                style: Theme.of(context).textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (final field in visible)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 7),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 126,
                    child: Text(
                      field.$2,
                      style: Theme.of(context).textTheme.bodySmall
                          ?.copyWith(color: colors.onSurfaceVariant),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: SelectableText(
                      details[field.$1].toString(),
                      style: Theme.of(context).textTheme.bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _section(
    BuildContext context,
    String title,
    List<Map<String, dynamic>> rows,
    String? Function(Map<String, dynamic>) label,
  ) {
    final titles = rows.map(label).whereType<String>().toSet().toList();
    if (titles.isEmpty) return const SizedBox.shrink();
    final colors = Theme.of(context).colorScheme;
    final isInterest = title == 'Centres d’intérêt';
    final isOpening = title == 'Ouvert à';
    final isDeclared = isInterest || isOpening;
    final icon = isInterest
        ? Icons.interests_outlined
        : isOpening
        ? Icons.handshake_outlined
        : title == 'Activités portées'
        ? Icons.event_available_outlined
        : title == 'Faits établis'
        ? Icons.verified_outlined
        : Icons.workspace_premium_outlined;
    return Padding(
      padding: const EdgeInsets.only(top: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 21, color: colors.primary),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              Text(
                '${titles.length}',
                style: Theme.of(context).textTheme.labelLarge
                    ?.copyWith(color: colors.onSurfaceVariant),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (isDeclared)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final value in titles)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 13,
                      vertical: 9,
                    ),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(100),
                      color: colors.primary.withValues(alpha: 0.07),
                      border: Border.all(
                        color: colors.primary.withValues(alpha: 0.15),
                      ),
                    ),
                    child: Text(
                      value,
                      style: Theme.of(context).textTheme.bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
              ],
            )
          else
            Column(
              children: [
                for (var index = 0; index < titles.length; index++) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: colors.primary.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(icon, size: 18, color: colors.primary),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            titles[index],
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (index != titles.length - 1)
                    Divider(height: 1, color: colors.outlineVariant),
                ],
              ],
            ),
        ],
      ),
    );
  }
}

class _PassportRecipientPicker extends StatefulWidget {
  const _PassportRecipientPicker({
    required this.api,
    required this.query,
    required this.onSelected,
  });

  final MakoloApiClient api;
  final TextEditingController query;
  final ValueChanged<Map<String, dynamic>> onSelected;

  @override
  State<_PassportRecipientPicker> createState() =>
      _PassportRecipientPickerState();
}

class _PassportRecipientPickerState extends State<_PassportRecipientPicker> {
  bool _searching = false;
  List<Map<String, dynamic>> _results = const [];

  Future<void> _search() async {
    final query = widget.query.text.trim();
    if (query.length < 2 || _searching) return;
    setState(() => _searching = true);
    try {
      final url = Uri(
        path: 'api/v1/sharing/recipients/',
        queryParameters: {'q': query},
      ).toString();
      final response = await widget.api.get(url);
      final values = response.jsonObject()['results'];
      if (!mounted) return;
      setState(() {
        _results = values is List
            ? values
                  .whereType<Map>()
                  .map(
                    (value) => value.map(
                      (key, value) => MapEntry(key.toString(), value),
                    ),
                  )
                  .toList()
            : const [];
      });
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recherche indisponible.')),
        );
      }
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        8,
        16,
        MediaQuery.viewInsetsOf(context).bottom + 16,
      ),
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height * 0.55,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Partager dans Makolo',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: widget.query,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                hintText: 'Nom ou identifiant',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: MakoloIconActionButton(
                  tooltip: 'Rechercher',
                  icon: Icons.arrow_forward,
                  onPressed: _searching ? null : _search,
                ),
                border: const OutlineInputBorder(),
              ),
            ),
            if (_searching) const LinearProgressIndicator(),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.builder(
                itemCount: _results.length,
                itemBuilder: (context, index) {
                  final row = _results[index];
                  return ListTile(
                    leading: const Icon(Icons.person_outline),
                    title: Text(row['name']?.toString() ?? ''),
                    subtitle: Text('@${row['username'] ?? ''}'),
                    onTap: () => widget.onSelected(row),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

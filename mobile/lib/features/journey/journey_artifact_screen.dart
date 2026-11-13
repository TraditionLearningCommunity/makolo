import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/files/profile_file_store.dart';
import '../../data/files/profile_paths.dart';
import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/files/system_file_picker.dart';
import '../../platform/media/private_media_views.dart';
import '../../sync/owner_source_state.dart';
import 'journey_artifact_repository.dart';

/// Native private Journey pieces. The owner API validates every mutation.
/// Local metadata is retained; file bytes are never cached as a public asset.
class JourneyArtifactScreen extends StatefulWidget {
  const JourneyArtifactScreen({
    super.key,
    required this.runtime,
    required this.journeyId,
    this.space,
  });

  final AppRuntime runtime;
  final String journeyId;
  final SpaceActorIdentity? space;

  @override
  State<JourneyArtifactScreen> createState() => _JourneyArtifactScreenState();
}

class _JourneyArtifactScreenState extends State<JourneyArtifactScreen> {
  static const _picker = NativeSystemFilePicker();
  static const _kinds = <String, String>{
    'other': 'Autre pièce',
    'cv': 'CV',
    'cover_letter': 'Lettre de motivation',
    'certificate': 'Certificat',
    'transcript': 'Relevé',
    'recommendation': 'Recommandation',
    'form': 'Formulaire',
    'identity_document': 'Document d’identité',
    'payment_receipt': 'Reçu de paiement',
  };
  final _title = TextEditingController();
  late JourneyArtifactRepository _repository;
  ProfileFileStore? _fileStore;
  StoredLocalFile? _staged;
  String? _filename;
  String? _versionOf;
  String _kind = 'other';
  String _sensitivity = 'sensitive';
  bool _loading = false;
  bool _busy = false;
  bool _denied = false;
  String? _message;
  int _epoch = 0;

  String get _intentId =>
      'journey-artifact:${_repository.profileId}:${widget.space?.id ?? 'profile'}:${widget.journeyId}';

  bool get _correctActor {
    final selected = widget.runtime.actorContext?.value;
    if (widget.space == null) return true;
    return selected is SpaceActorContext && selected.space == widget.space;
  }

  String get _path =>
      JourneyArtifactRepository.path(widget.journeyId, space: widget.space);

  @override
  void initState() {
    super.initState();
    _repository = _openRepository();
    widget.runtime.actorContext?.addListener(_actorChanged);
    unawaited(_restore());
    unawaited(_refresh());
  }

  JourneyArtifactRepository _openRepository() => JourneyArtifactRepository(
    database: widget.runtime.database!,
    store: widget.runtime.store!,
    profileId: widget.runtime.session!.profileId,
    sync: widget.runtime.sync,
  );

  @override
  void didUpdateWidget(covariant JourneyArtifactScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_actorChanged);
      widget.runtime.actorContext?.addListener(_actorChanged);
    }
    if (oldWidget.journeyId != widget.journeyId ||
        oldWidget.space != widget.space ||
        oldWidget.runtime != widget.runtime) {
      _epoch++;
      _repository = _openRepository();
      _staged = null;
      _fileStore = null;
      _message = null;
      _denied = false;
      unawaited(_restore());
      unawaited(_refresh());
    }
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_actorChanged);
    _title.dispose();
    super.dispose();
  }

  void _actorChanged() {
    if (!mounted) return;
    setState(() {
      _denied = !_correctActor;
      _message = null;
    });
    if (_correctActor) unawaited(_refresh());
  }

  Future<ProfileFileStore> _files() async {
    return _fileStore ??= await ProfileFileStore.open(
      database: _repository.database,
      profileId: _repository.profileId,
    );
  }

  Future<void> _restore() async {
    final epoch = _epoch;
    try {
      final remembered = await widget.runtime.interactions?.read(_intentId);
      final fileId = remembered?['file_id'];
      final staged = fileId is String
          ? await (await _files()).read(fileId)
          : null;
      if (!mounted || epoch != _epoch) return;
      setState(() {
        _staged = staged;
        _title.text = remembered?['title'] is String
            ? remembered!['title'] as String
            : '';
        _kind = _kinds.containsKey(remembered?['kind'])
            ? remembered!['kind'] as String
            : 'other';
        _sensitivity =
            const {
              'normal',
              'sensitive',
              'restricted',
            }.contains(remembered?['sensitivity'])
            ? remembered!['sensitivity'] as String
            : 'sensitive';
        _versionOf = remembered?['version_of'] is String
            ? remembered!['version_of'] as String
            : null;
        _filename = remembered?['filename'] is String
            ? remembered!['filename'] as String
            : null;
      });
    } on Object {
      // A missing draft does not erase owner data or invent a server result.
    }
  }

  Future<void> _saveDraft() async {
    await widget.runtime.interactions?.save(_intentId, {
      'file_id': _staged?.fileId,
      'filename': _filename,
      'title': _title.text.trim(),
      'kind': _kind,
      'sensitivity': _sensitivity,
      'version_of': _versionOf,
    });
  }

  Future<void> _refresh() async {
    if (_loading || !_correctActor) return;
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      await _repository.refresh(widget.journeyId, space: widget.space);
      if (mounted) setState(() => _denied = false);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      if (error.statusCode == 403 || error.statusCode == 404) {
        await _repository.store.deleteProjection(
          JourneyArtifactRepository.projectionKind,
          resourceKey: JourneyArtifactRepository.resourceKey(
            widget.journeyId,
            space: widget.space,
          ),
        );
        if (mounted) setState(() => _denied = true);
      } else {
        setState(() {
          _message = 'Impossible d’actualiser les pièces. Les données locales restent disponibles.';
        });
      }
    } on Object {
      if (mounted) {
        setState(() {
          _message = 'Actualisation indisponible. Les pièces déjà connues restent visibles.';
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pick() async {
    if (_busy || !_correctActor) return;
    try {
      final selected = await _picker.pick(
        allowedExtensions: ['pdf', 'docx', 'doc', 'txt', 'jpg', 'jpeg', 'png'],
      );
      if (selected.isEmpty) return;
      final file = selected.first;
      final store = await _files();
      final random = Random.secure();
      final fileId =
          'journey-piece-${DateTime.now().microsecondsSinceEpoch}-${random.nextInt(1 << 30)}';
      final staged = await store.stageCopy(
        fileId: fileId,
        owner: 'JourneyArtifact',
        sourceFilename: file.name,
        purpose: 'service_journey_attachment',
        sensitivity: _sensitivity,
        writeTo: file.copyTo,
      );
      if (!mounted || !_correctActor) return;
      final previous = _staged;
      setState(() {
        _staged = staged;
        _filename = file.name;
      });
      await _saveDraft();
      if (previous != null) await store.remove(previous.fileId);
    } on Object {
      if (mounted) {
        setState(() {
          _message =
              'La pièce n’a pas été préparée. Votre brouillon est conservé.';
        });
      }
    }
  }

  Future<void> _send() async {
    final local = _staged;
    final api = widget.runtime.api;
    if (_busy || !_correctActor || local == null || api == null) return;
    if (_versionOf == null && _title.text.trim().isEmpty) {
      setState(() => _message = 'Donnez un nom à cette pièce.');
      return;
    }
    if (_kind == 'identity_document' && _sensitivity != 'restricted') {
      setState(() => _message = 'Une pièce d’identité doit être restreinte.');
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await _saveDraft();
      final endpoint = _versionOf == null
          ? _path
          : '$_path${_versionOf!}/versions/';
      final response = await api.upload(
        endpoint,
        fields: _versionOf == null
            ? {
                'title': _title.text.trim(),
                'kind': _kind,
                'sensitivity': _sensitivity,
              }
            : {'sensitivity': _sensitivity},
        files: [
          MakoloUploadFile(
            fieldName: 'file',
            path: local.path,
            filename: _filename,
            contentType: _mime(_filename),
          ),
        ],
      );
      final result = response.jsonObject();
      if (result['id'] is! String ||
          result['journey_id'] != widget.journeyId ||
          !{200, 201}.contains(response.statusCode)) {
        throw const FormatException('Owner did not confirm JourneyArtifact');
      }
      if (!mounted) return;
      setState(() {
        _staged = null;
        _filename = null;
        _versionOf = null;
        _title.clear();
        _message = 'Pièce reçue par Makolo. Elle n’est pas automatiquement validée comme condition.';
      });
      await widget.runtime.interactions?.clear(_intentId);
      await (await _files()).remove(local.fileId);
      unawaited(_refresh());
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _message = error.statusCode == 409
            ? 'Une version ou une pièce différente existe déjà. Vérifiez la liste avant de réessayer.'
            : error.statusCode == 403 || error.statusCode == 404
            ? 'L’accès à cette démarche n’est plus autorisé.'
            : 'La pièce n’a pas été confirmée. Le fichier reste dans votre brouillon privé.';
      });
      if (error.statusCode == 403 || error.statusCode == 404) {
        unawaited(_refresh());
      }
    } on Object {
      if (mounted) {
        setState(() {
          _message = 'La confirmation n’a pas été reçue. Réessayez sans changer la pièce.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _newVersion(Map<String, dynamic> artifact) async {
    if (_busy || !_correctActor) return;
    setState(() {
      _versionOf = artifact['id']?.toString();
      _title.text = artifact['title']?.toString() ?? '';
      _kind = artifact['kind']?.toString() ?? 'other';
      _sensitivity = artifact['sensitivity']?.toString() ?? 'sensitive';
      _staged = null;
      _filename = null;
      _message = 'Choisissez le fichier qui remplacera cette version.';
    });
    await _saveDraft();
  }

  @override
  Widget build(BuildContext context) {
    final valid = _correctActor && !_denied;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pièces de ma démarche'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _loading || !valid ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: !valid
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Ce dossier n’est plus accessible dans ce contexte.',
                ),
              ),
            )
          : StreamBuilder<StoredProjection?>(
              stream: _repository.watch(widget.journeyId, space: widget.space),
              builder: (context, snapshot) {
                final payload = snapshot.data?.payload;
                final raw = payload?['artifacts'];
                final pieces = raw is List
                    ? raw
                          .whereType<Map>()
                          .map((row) => Map<String, dynamic>.from(row))
                          .toList()
                    : <Map<String, dynamic>>[];
                final canUpload =
                    payload?['capabilities'] is Map &&
                    (payload!['capabilities'] as Map)['upload'] == true;
                return ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    if (_loading) const LinearProgressIndicator(),
                    if (_message != null) ...[
                      const SizedBox(height: 12),
                      Text(_message!),
                    ],
                    if (snapshot.data == null && !_loading)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 18),
                        child: Text(
                          'Aucune liste locale disponible. Actualisez pour consulter vos pièces.',
                        ),
                      ),
                    if (snapshot.data != null && pieces.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 18),
                        child: Text(
                          'Aucune pièce enregistrée pour cette démarche.',
                        ),
                      ),
                    for (final piece in pieces)
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                piece['title']?.toString() ?? 'Pièce',
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              Text(
                                'Version ${piece['version']} · ${piece['status']}',
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                children: [
                                  if (piece['capabilities'] is Map &&
                                      (piece['capabilities']
                                              as Map)['download'] ==
                                          true)
                                    MakoloActionButton(
                                      label: 'Lire',
                                      icon: Icons.visibility_outlined,
                                      onPressed: _busy
                                          ? null
                                          : () {
                                              final download =
                                                  piece['links'] is Map
                                                  ? (piece['links']
                                                        as Map)['download']
                                                  : null;
                                              if (download is String &&
                                                  download.isNotEmpty) {
                                                Navigator.of(context).push(
                                                  MaterialPageRoute<void>(
                                                    builder: (_) =>
                                                        _PrivatePieceReader(
                                                          api: widget
                                                              .runtime
                                                              .api!,
                                                          profileId: _repository
                                                              .profileId,
                                                          path: download,
                                                          title:
                                                              piece['title']
                                                                  ?.toString() ??
                                                              'Pièce',
                                                          mime:
                                                              piece['mime_type']
                                                                  ?.toString() ??
                                                              '',
                                                        ),
                                                  ),
                                                );
                                              }
                                            },
                                    ),
                                  if (canUpload &&
                                      piece['capabilities'] is Map &&
                                      (piece['capabilities']
                                              as Map)['new_version'] ==
                                          true)
                                    MakoloActionButton(
                                      label: 'Nouvelle version',
                                      icon: Icons.history_rounded,
                                      onPressed: _busy
                                          ? null
                                          : () => _newVersion(piece),
                                    ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    if (canUpload) ...[
                      const SizedBox(height: 18),
                      Text(
                        _versionOf == null
                            ? 'Ajouter une pièce'
                            : 'Nouvelle version',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      if (_versionOf == null)
                        TextField(
                          controller: _title,
                          maxLength: 220,
                          decoration: const InputDecoration(
                            labelText: 'Nom de la pièce',
                          ),
                        ),
                      if (_versionOf == null)
                        DropdownButtonFormField<String>(
                          initialValue: _kind,
                          decoration: const InputDecoration(labelText: 'Type'),
                          items: _kinds.entries
                              .map(
                                (item) => DropdownMenuItem(
                                  value: item.key,
                                  child: Text(item.value),
                                ),
                              )
                              .toList(),
                          onChanged: _busy
                              ? null
                              : (value) {
                                  if (value != null)
                                    setState(() => _kind = value);
                                },
                        ),
                      DropdownButtonFormField<String>(
                        initialValue: _sensitivity,
                        decoration: const InputDecoration(
                          labelText: 'Confidentialité',
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: 'normal',
                            child: Text('Normale'),
                          ),
                          DropdownMenuItem(
                            value: 'sensitive',
                            child: Text('Sensible'),
                          ),
                          DropdownMenuItem(
                            value: 'restricted',
                            child: Text('Restreinte'),
                          ),
                        ],
                        onChanged: _busy
                            ? null
                            : (value) {
                                if (value != null)
                                  setState(() => _sensitivity = value);
                              },
                      ),
                      const SizedBox(height: 12),
                      if (_filename != null) Text(_filename!),
                      MakoloActionButton(
                        label: _filename == null
                            ? 'Choisir un fichier'
                            : 'Remplacer le fichier choisi',
                        icon: Icons.attach_file_rounded,
                        onPressed: _busy ? null : _pick,
                      ),
                      const SizedBox(height: 8),
                      MakoloActionButton(
                        label: _versionOf == null
                            ? 'Ajouter à ma démarche'
                            : 'Envoyer cette version',
                        icon: Icons.file_upload_outlined,
                        appearance: MakoloActionAppearance.primary,
                        onPressed: _busy || _staged == null ? null : _send,
                        busy: _busy,
                      ),
                    ],
                  ],
                );
              },
            ),
    );
  }
}

String? _mime(String? filename) {
  final ext = (filename ?? '').split('.').last.toLowerCase();
  return switch (ext) {
    'pdf' => 'application/pdf',
    'txt' => 'text/plain',
    'doc' => 'application/msword',
    'docx' =>
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'jpg' || 'jpeg' => 'image/jpeg',
    'png' => 'image/png',
    _ => null,
  };
}

class _PrivatePieceReader extends StatefulWidget {
  const _PrivatePieceReader({
    required this.api,
    required this.profileId,
    required this.path,
    required this.title,
    required this.mime,
  });

  final MakoloApiClient api;
  final String profileId;
  final String path;
  final String title;
  final String mime;

  @override
  State<_PrivatePieceReader> createState() => _PrivatePieceReaderState();
}

class _PrivatePieceReaderState extends State<_PrivatePieceReader> {
  String? _path;
  bool _busy = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    if (!const {
      'application/pdf',
      'image/jpeg',
      'image/png',
      'text/plain',
    }.contains(widget.mime)) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = 'Ce format ne peut pas être prévisualisé dans Makolo.';
        });
      }
      return;
    }
    final suffix = switch (widget.mime) {
      'application/pdf' => 'pdf',
      'image/jpeg' => 'jpg',
      'image/png' => 'png',
      _ => 'txt',
    };
    try {
      final root = await ProfilePaths.reconstructibleCache(widget.profileId);
      final folder = Directory(
        '${root.path}/journey-reader-${DateTime.now().microsecondsSinceEpoch}',
      );
      await folder.create(recursive: true);
      final local = '${folder.path}/piece.$suffix';
      await widget.api.download(widget.path, destinationPath: local);
      if (!mounted) {
        await _clear(local);
        return;
      }
      setState(() {
        _path = local;
        _busy = false;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = 'Impossible d’ouvrir la pièce actuellement.';
        });
      }
    }
  }

  Future<void> _clear(String path) async {
    try {
      await File(path).parent.delete(recursive: true);
    } on FileSystemException {
      // Reader bytes are temporary and Profile-scoped.
    }
  }

  @override
  void dispose() {
    final path = _path;
    if (path != null) unawaited(_clear(path));
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: _busy
        ? const Center(child: CircularProgressIndicator.adaptive())
        : _error != null
        ? Center(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Text(_error!),
            ),
          )
        : _reader(),
  );

  Widget _reader() {
    final path = _path;
    if (path == null) return const Center(child: Text('Pièce indisponible.'));
    if (widget.mime == 'application/pdf') return PrivatePdfView(path: path);
    if (widget.mime == 'text/plain') {
      return FutureBuilder<String>(
        future: File(path).readAsString(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator.adaptive());
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: SelectableText(snapshot.data!),
          );
        },
      );
    }
    return InteractiveViewer(child: Center(child: Image.file(File(path))));
  }
}

import '../../platform/media/native_media_picker.dart';

import 'dart:io';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../platform/files/native_directories.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/downloads/device_downloads.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../platform/media/private_media_views.dart';

/// Space-owned document N3: owner actions and versioned private file transfer.
class SpaceDocumentDetailScreen extends StatefulWidget {
  const SpaceDocumentDetailScreen({
    super.key,
    required this.runtime,
    required this.slug,
    required this.documentId,
  });

  final AppRuntime runtime;
  final String slug;
  final String documentId;

  @override
  State<SpaceDocumentDetailScreen> createState() =>
      _SpaceDocumentDetailScreenState();
}

class _SpaceDocumentDetailScreenState extends State<SpaceDocumentDetailScreen> {
  Map<String, dynamic>? _document;
  List<Map<String, dynamic>> _shares = [];
  bool _canManage = false;
  bool _loading = true;
  bool _working = false;
  bool _previewOpen = false;
  int _request = 0;
  String? _error;

  SpaceActorContext? get _actor {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == widget.slug
        ? actor
        : null;
  }

  String get _base =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/documents/';

  String get _url => '$_base${Uri.encodeComponent(widget.documentId)}/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _request++;
    widget.runtime.actorContext?.removeListener(_actorChanged);
    super.dispose();
  }

  void _actorChanged() {
    if (_previewOpen && mounted) {
      _previewOpen = false;
      Navigator.of(context).maybePop();
    }
    _request++;
    if (!mounted) return;
    setState(() {
      _document = null;
      _shares = [];
      _canManage = false;
      _error = _actor == null ? 'Cet Espace n’est plus actif.' : null;
      _loading = _actor != null;
    });
    if (_actor != null) _load();
  }

  Future<void> _load() async {
    final api = widget.runtime.api;
    final id = _actor?.space.id;
    final ticket = ++_request;
    if (api == null || id == null) {
      if (!mounted) return;
      setState(() {
        _document = null;
        _loading = false;
        _error = id == null
            ? 'Cet Espace n’est plus actif.'
            : 'Connexion nécessaire.';
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final payload = (await api.get(_url)).jsonObject();
      if (!mounted || ticket != _request || _actor?.space.id != id) return;
      final doc = payload['document'];
      if (doc is! Map<String, dynamic> || doc['id'] != widget.documentId) {
        throw const FormatException('Document incohérent');
      }
      setState(() {
        _document = doc;
        _canManage = payload['can_manage'] == true;
        _shares = _canManage
            ? [
                for (final share in payload['shares'] as List? ?? [])
                  if (share is Map<String, dynamic>) share,
              ]
            : [];
        _loading = false;
      });
    } on Object {
      if (!mounted || ticket != _request || _actor?.space.id != id) return;
      setState(() {
        _document = null;
        _shares = [];
        _canManage = false;
        _error = 'Document indisponible.';
        _loading = false;
      });
    }
  }

  Future<void> _replace() async {
    if (_working || !_canManage || _actor == null) return;
    final file = await NativeMediaPicker.pickDocument([
      'pdf',
      'doc',
      'docx',
      'txt',
      'png',
      'jpg',
      'jpeg',
    ]);
    if (file == null || !mounted) return;
    if (file.path == null) return;
    final id = _actor?.space.id;
    final api = widget.runtime.api;
    if (id == null || api == null) return;
    setState(() => _working = true);
    try {
      await api.upload(
        '${_url}versions/',
        files: [
          MakoloUploadFile(
            fieldName: 'file',
            path: file.path!,
            filename: file.name,
          ),
        ],
      );
      if (!mounted || _actor?.space.id != id) return;
      _toast('Version ajoutée.');
      await _load();
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Ajout impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _download(Map<String, dynamic> version) async {
    if (_working || _actor == null) return;
    final api = widget.runtime.api;
    final id = _actor!.space.id;
    final versionId = version['id']?.toString();
    if (api == null || versionId == null) return;
    final mime = version['mime_type']?.toString() ?? 'application/octet-stream';
    final ext = switch (mime) {
      'application/pdf' => 'pdf',
      'image/jpeg' => 'jpg',
      'image/png' => 'png',
      'text/plain' => 'txt',
      'application/msword' => 'doc',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document' =>
        'docx',
      _ => 'bin',
    };
    final safeName = makoloDownloadName(
      '${_document?['title'] ?? 'Document'}-v${version['number']}',
      ext,
    );
    final temporary = await NativeDirectories.temporary();
    final folder = await Directory(
      '${temporary.path}/makolo-export-${DateTime.now().microsecondsSinceEpoch}',
    ).create();
    final file = File('${folder.path}/$safeName');
    setState(() => _working = true);
    try {
      await api.download(
        '${_base}versions/${Uri.encodeComponent(versionId)}/download/',
        destinationPath: file.path,
      );
      if (!mounted || _actor?.space.id != id) return;
      if (Platform.isAndroid) {
        await const AndroidDeviceDownloads().save(
          source: file,
          fileName: safeName,
          mimeType: mime,
        );
      } else {
        await const SystemShareGateway().shareFiles(paths: [file.path]);
      }
      if (mounted && _actor?.space.id == id) _toast('Document enregistré.');
    } on Object {
      if (mounted && _actor?.space.id == id) {
        _toast('Téléchargement impossible.');
      }
    } finally {
      if (await folder.exists()) await folder.delete(recursive: true);
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _preview(Map<String, dynamic> version) async {
    if (_working || _actor == null) return;
    final mime = version['mime_type']?.toString();
    if (mime != 'application/pdf' &&
        mime != 'image/jpeg' &&
        mime != 'image/png') {
      return;
    }
    final api = widget.runtime.api;
    final spaceId = _actor!.space.id;
    final versionId = version['id']?.toString();
    if (api == null || versionId == null) return;
    final directory = await NativeDirectories.temporary();
    final folder = await Directory(
      '${directory.path}/makolo-preview-${DateTime.now().microsecondsSinceEpoch}',
    ).create();
    final extension = mime == 'application/pdf'
        ? 'pdf'
        : mime == 'image/png'
        ? 'png'
        : 'jpg';
    final file = File('${folder.path}/document.$extension');
    if (!mounted || _actor?.space.id != spaceId) {
      if (await folder.exists()) await folder.delete(recursive: true);
      return;
    }
    setState(() => _working = true);
    try {
      await api.download(
        '${_base}versions/${Uri.encodeComponent(versionId)}/download/',
        destinationPath: file.path,
      );
      if (!mounted || _actor?.space.id != spaceId) return;
      setState(() => _working = false);
      _previewOpen = true;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (previewContext) => Scaffold(
            appBar: AppBar(title: const Text('Document')),
            body: mime == 'application/pdf'
                ? PrivatePdfView(path: file.path)
                : InteractiveViewer(child: Center(child: Image.file(file))),
          ),
        ),
      );
    } on Object {
      if (mounted && _actor?.space.id == spaceId) {
        _toast('Aperçu indisponible.');
      }
    } finally {
      _previewOpen = false;
      if (await folder.exists()) await folder.delete(recursive: true);
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _share(Map<String, dynamic> version) async {
    if (_working || !_canManage || _actor == null) return;
    final controller = TextEditingController();
    var days = 7;
    final recipient = await showDialog<String>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Partager'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: controller,
                autofocus: true,
                decoration: const InputDecoration(
                  prefixText: '@',
                  labelText: 'Destinataire Makolo',
                ),
              ),
              DropdownButtonFormField<int>(
                initialValue: days,
                decoration: const InputDecoration(labelText: 'Durée'),
                items: const [
                  DropdownMenuItem(value: 1, child: Text('1 jour')),
                  DropdownMenuItem(value: 7, child: Text('7 jours')),
                  DropdownMenuItem(value: 30, child: Text('30 jours')),
                ],
                onChanged: (value) => update(() => days = value ?? 7),
              ),
            ],
          ),
          actions: [
            MakoloActionButton(
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialogContext),
              label: 'Annuler',
            ),
            MakoloActionButton(
              appearance: MakoloActionAppearance.primary,
              onPressed: () =>
                  Navigator.pop(dialogContext, controller.text.trim()),
              label: 'Partager',
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (recipient == null || recipient.isEmpty || _actor == null) return;
    final id = _actor!.space.id;
    final api = widget.runtime.api;
    if (api == null) return;
    setState(() => _working = true);
    try {
      await api.post(
        '${_base}versions/${Uri.encodeComponent(version['id'].toString())}/share/',
        body: {
          'recipient_username': recipient.startsWith('@')
              ? recipient.substring(1)
              : recipient,
          'days': days,
        },
      );
      if (mounted && _actor?.space.id == id) {
        _toast('Document partagé.');
        await _load();
      }
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Partage impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _revoke(String deliveryId) async {
    if (_working || !_canManage || _actor == null) return;
    final id = _actor!.space.id;
    final api = widget.runtime.api;
    if (api == null) return;
    setState(() => _working = true);
    try {
      await api.post(
        '${_base}shares/${Uri.encodeComponent(deliveryId)}/revoke/',
      );
      if (mounted && _actor?.space.id == id) {
        _toast('Partage révoqué.');
        await _load();
      }
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Révocation impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _reuse(Map<String, dynamic> version) async {
    if (_working || _actor == null) return;
    final api = widget.runtime.api;
    final id = _actor!.space.id;
    if (api == null) return;
    List<Map<String, dynamic>> journeys;
    try {
      final response = (await api.get('${_base}eligible-journeys/'))
          .jsonObject();
      if (!mounted || _actor?.space.id != id || response['space_id'] != id) {
        return;
      }
      journeys = [
        for (final row in response['items'] as List? ?? [])
          if (row is Map<String, dynamic>) row,
      ];
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Démarches indisponibles.');
      return;
    }
    if (!mounted || journeys.isEmpty) {
      if (mounted && _actor?.space.id == id) {
        _toast('Aucune démarche disponible.');
      }
      return;
    }
    final journeyId = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            Padding(
              padding: const EdgeInsets.all(MakoloSpacing.md),
              child: Text(
                'Choisir une démarche',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            for (final journey in journeys)
              ListTile(
                leading: const Icon(Icons.route_outlined),
                title: Text(journey['title']?.toString() ?? 'Démarche'),
                onTap: () =>
                    Navigator.pop(sheetContext, journey['id']?.toString()),
              ),
          ],
        ),
      ),
    );
    if (journeyId == null || _actor?.space.id != id) return;
    setState(() => _working = true);
    try {
      await api.post(
        '${_base}versions/${Uri.encodeComponent(version['id'].toString())}/reuse/',
        body: {'journey_id': journeyId},
      );
      if (mounted && _actor?.space.id == id) _toast('Ajouté à la démarche.');
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Ajout impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _edit() async {
    final doc = _document;
    if (_working || !_canManage || doc == null || _actor == null) return;
    final controller = TextEditingController(
      text: doc['title']?.toString() ?? '',
    );
    var visibility = doc['visibility']?.toString() ?? 'restricted';
    final changes = await showDialog<Map<String, String>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Modifier'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: controller,
                maxLength: 220,
                decoration: const InputDecoration(labelText: 'Titre'),
              ),
              DropdownButtonFormField<String>(
                initialValue: visibility,
                decoration: const InputDecoration(labelText: 'Accès'),
                items: const [
                  DropdownMenuItem(
                    value: 'restricted',
                    child: Text('Confidentiel'),
                  ),
                  DropdownMenuItem(
                    value: 'internal',
                    child: Text('Équipe autorisée'),
                  ),
                ],
                onChanged: (value) =>
                    update(() => visibility = value ?? 'restricted'),
              ),
            ],
          ),
          actions: [
            MakoloActionButton(
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialogContext),
              label: 'Annuler',
            ),
            MakoloActionButton(
              appearance: MakoloActionAppearance.primary,
              onPressed: () {
                if (controller.text.trim().isNotEmpty) {
                  Navigator.pop(dialogContext, {
                    'title': controller.text.trim(),
                    'visibility': visibility,
                  });
                }
              },
              label: 'Enregistrer',
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (changes == null || _actor == null) return;
    final id = _actor!.space.id;
    setState(() => _working = true);
    try {
      await widget.runtime.api!.patch(_url, body: changes);
      if (mounted && _actor?.space.id == id) {
        _toast('Document actualisé.');
        await _load();
      }
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Modification impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _archive() async {
    if (_working || !_canManage || _actor == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Archiver ce document ?'),
        actions: [
          MakoloActionButton(
            appearance: MakoloActionAppearance.quiet,
            onPressed: () => Navigator.pop(dialogContext, false),
            label: 'Annuler',
          ),
          MakoloActionButton(
            appearance: MakoloActionAppearance.primary,
            onPressed: () => Navigator.pop(dialogContext, true),
            label: 'Archiver',
          ),
        ],
      ),
    );
    if (confirmed != true || _actor == null) return;
    final id = _actor!.space.id;
    setState(() => _working = true);
    try {
      await widget.runtime.api!.delete(_url);
      if (!mounted || _actor?.space.id != id) return;
      context.pop();
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Archivage impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final doc = _document;
    final versions = <Map<String, dynamic>>[
      for (final row in doc?['versions'] as List? ?? [])
        if (row is Map<String, dynamic>) row,
    ];
    final colors = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Document'),
        actions: [
          if (_canManage)
            MakoloIconActionButton(
              tooltip: 'Modifier',
              onPressed: _working ? null : _edit,
              icon: Icons.edit_outlined,
            ),
          if (_canManage)
            MakoloIconActionButton(
              tooltip: 'Archiver',
              onPressed: _working ? null : _archive,
              icon: Icons.archive_outlined,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : doc == null
          ? const Center(child: Text('Document indisponible.'))
          : ListView(
              padding: const EdgeInsets.all(MakoloSpacing.lg),
              children: [
                Icon(
                  Icons.description_outlined,
                  size: 44,
                  color: colors.primary,
                ),
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  doc['title']?.toString() ?? 'Document',
                  style: text.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.sm),
                Text(
                  doc['visibility'] == 'restricted'
                      ? 'Confidentiel'
                      : 'Équipe autorisée',
                ),
                const SizedBox(height: MakoloSpacing.xl),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Versions',
                        style: text.titleLarge?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    if (_canManage)
                      MakoloIconActionButton(
                        tooltip: 'Nouvelle version',
                        onPressed: _working ? null : _replace,
                        icon: Icons.add_circle_outline,
                      ),
                  ],
                ),
                for (final version in versions)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.history_rounded),
                      title: Text('Version ${version['number']}'),
                      subtitle: Text(
                        version['mime_type']?.toString() ?? 'Document',
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (version['mime_type'] == 'application/pdf' ||
                              version['mime_type'] == 'image/jpeg' ||
                              version['mime_type'] == 'image/png')
                            MakoloIconActionButton(
                              tooltip: 'Ouvrir',
                              onPressed: _working
                                  ? null
                                  : () => _preview(version),
                              icon: Icons.visibility_outlined,
                            ),
                          MakoloIconActionButton(
                            tooltip: 'Télécharger',
                            onPressed: _working
                                ? null
                                : () => _download(version),
                            icon: Icons.download_rounded,
                          ),
                          if (_canManage)
                            MakoloIconActionButton(
                              tooltip: 'Partager',
                              onPressed: _working
                                  ? null
                                  : () => _share(version),
                              icon: Icons.share_outlined,
                            ),
                          MakoloIconActionButton(
                            tooltip: 'Utiliser',
                            onPressed: _working ? null : () => _reuse(version),
                            icon: Icons.arrow_outward_rounded,
                          ),
                        ],
                      ),
                    ),
                  ),
                if (_canManage && _shares.isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.xl),
                  Text(
                    'Partages',
                    style: text.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  for (final share in _shares)
                    ListTile(
                      leading: const Icon(Icons.person_outline_rounded),
                      title: Text('@${share['recipient'] ?? ''}'),
                      subtitle: Text(
                        share['active'] == true ? 'Actif' : 'Terminé',
                      ),
                      trailing: share['active'] == true
                          ? MakoloIconActionButton(
                              tooltip: 'Révoquer',
                              onPressed: _working
                                  ? null
                                  : () => _revoke(share['id'].toString()),
                              icon: Icons.close_rounded,
                            )
                          : null,
                    ),
                ],
                const SizedBox(height: 70),
              ],
            ),
    );
  }
}

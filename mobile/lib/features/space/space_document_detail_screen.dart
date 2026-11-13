import '../../platform/media/native_media_picker.dart';

import 'dart:io';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../platform/files/native_directories.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../sync/owner_source_state.dart';
import 'space_repository.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/downloads/device_downloads.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../platform/media/private_media_views.dart';
import '../resources/resource_presentation.dart';

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
  bool _canUseNetwork = false;
  bool _initializing = true;
  bool _refreshing = false;
  bool _working = false;
  bool _previewOpen = false;

  SpaceActorContext? get _actor {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == widget.slug
        ? actor
        : null;
  }

  String get _base =>
      'api/v1/organizations/workspaces/'
      '${Uri.encodeComponent(widget.slug)}/documents/';

  String get _url =>
      '$_base${Uri.encodeComponent(widget.documentId)}/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_ensure());
    });
  }

  @override
  void didUpdateWidget(covariant SpaceDocumentDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.slug != widget.slug ||
        oldWidget.documentId != widget.documentId) {
      oldWidget.runtime.actorContext?.removeListener(_actorChanged);
      widget.runtime.actorContext?.addListener(_actorChanged);
      _actorChanged();
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_actorChanged);
    super.dispose();
  }

  void _actorChanged() {
    if (_previewOpen && mounted) {
      _previewOpen = false;
      Navigator.of(context).maybePop();
    }
    if (!mounted) return;
    setState(() {
      _document = null;
      _shares = [];
      _canManage = false;
      _canUseNetwork = false;
      _initializing = _actor != null;
      _refreshing = false;
    });
    if (_actor != null) unawaited(_ensure());
  }

  Future<void> _ensure() async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) {
      if (mounted) setState(() => _initializing = false);
      return;
    }
    final expectedId = actor.space.id;
    if (mounted) setState(() => _initializing = true);
    try {
      await repository.ensureDocumentDetail(
        actor.space,
        widget.documentId,
      );
    } on Object {
      // The last acquired owner projection remains readable.
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _initializing = false);
      }
    }
  }

  Future<void> _load() async {
    if (_refreshing) return;
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    final expectedId = actor.space.id;
    setState(() => _refreshing = true);
    try {
      await repository.refreshDocumentDetail(
        actor.space,
        widget.documentId,
      );
    } on Object {
      // The last acquired owner projection remains readable.
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _reconcileAfterMutation({
    bool collection = false,
    bool resources = false,
  }) async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    await _load();
    if (collection) {
      try {
        await repository.refreshDocumentPage(actor.space, query: '', offset: 0);
      } on Object {
        // Mutation is already confirmed; collection refresh is best effort.
      }
    }
    if (resources) {
      try {
        await repository.refreshResources(actor.space);
        await repository.refreshUs(actor.space);
      } on Object {
        // Hub reconciliation is best effort after owner confirmation.
      }
    }
  }

  Future<void> _replace() async {
    if (_working || !_canManage || !_canUseNetwork || _actor == null) return;
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
      await _reconcileAfterMutation(collection: true);
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Ajout impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _download(Map<String, dynamic> version) async {
    if (_working || !_canUseNetwork || _actor == null) return;
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
    if (_working || !_canUseNetwork || _actor == null) return;
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
    if (_working || !_canManage || !_canUseNetwork || _actor == null) return;
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
        await _reconcileAfterMutation();
      }
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Partage impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _revoke(String deliveryId) async {
    if (_working || !_canManage || !_canUseNetwork || _actor == null) return;
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
        await _reconcileAfterMutation();
      }
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Révocation impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _reuse(Map<String, dynamic> version) async {
    if (_working || !_canUseNetwork || _actor == null) return;
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
        await _reconcileAfterMutation(collection: true);
      }
    } on Object {
      if (mounted && _actor?.space.id == id) _toast('Modification impossible.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _archive() async {
    if (_working || !_canManage || !_canUseNetwork || _actor == null) return;
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
      final repository = widget.runtime.space;
      final actor = _actor;
      if (repository != null && actor != null && repository.sync != null) {
        try {
          await repository.refreshDocumentPage(
            actor.space,
            query: '',
            offset: 0,
          );
          await repository.refreshResources(actor.space);
          await repository.refreshUs(actor.space);
        } on Object {
          // Archive is already owner-confirmed; reconciliation is best effort.
        }
      }
      if (mounted && _actor?.space.id == id) context.pop();
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
    final currentVersion = versions.isEmpty ? null : versions.first;
    final previousVersions = versions.length <= 1
        ? const <Map<String, dynamic>>[]
        : versions.skip(1).toList(growable: false);

    bool canPreview(Map<String, dynamic> version) =>
        version['mime_type'] == 'application/pdf' ||
        version['mime_type'] == 'image/jpeg' ||
        version['mime_type'] == 'image/png';

    List<Widget> previousVersionActions(Map<String, dynamic> version) => [
      MakoloIconActionButton(
        tooltip: 'Télécharger',
        onPressed: _working ? null : () => _download(version),
        icon: Icons.download_rounded,
      ),
      PopupMenuButton<String>(
        tooltip: 'Plus',
        enabled: !_working,
        onSelected: (value) {
          if (value == 'share') {
            _share(version);
          } else if (value == 'reuse') {
            _reuse(version);
          }
        },
        itemBuilder: (context) => [
          if (_canManage)
            const PopupMenuItem(
              value: 'share',
              child: ListTile(
                leading: Icon(Icons.share_outlined),
                title: Text('Partager'),
                contentPadding: EdgeInsets.zero,
              ),
            ),
          const PopupMenuItem(
            value: 'reuse',
            child: ListTile(
              leading: Icon(Icons.drive_file_move_outline),
              title: Text('Utiliser dans une démarche'),
              contentPadding: EdgeInsets.zero,
            ),
          ),
        ],
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Document'),
        actions: [
          if (currentVersion != null)
            MakoloIconActionButton(
              tooltip: 'Télécharger',
              onPressed: _working ? null : () => _download(currentVersion),
              icon: Icons.download_rounded,
            ),
          if (currentVersion != null && _canManage)
            MakoloIconActionButton(
              tooltip: 'Partager',
              onPressed: _working ? null : () => _share(currentVersion),
              icon: Icons.share_outlined,
            ),
          PopupMenuButton<String>(
            tooltip: 'Plus',
            enabled: !_working,
            onSelected: (value) {
              if (value == 'reuse' && currentVersion != null) {
                _reuse(currentVersion);
              } else if (value == 'edit') {
                _edit();
              } else if (value == 'archive') {
                _archive();
              } else if (value == 'refresh') {
                _load();
              }
            },
            itemBuilder: (context) => [
              if (currentVersion != null)
                const PopupMenuItem(
                  value: 'reuse',
                  child: ListTile(
                    leading: Icon(Icons.drive_file_move_outline),
                    title: Text('Utiliser dans une démarche'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              if (_canManage)
                const PopupMenuItem(
                  value: 'edit',
                  child: ListTile(
                    leading: Icon(Icons.edit_outlined),
                    title: Text('Modifier'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              if (_canManage)
                const PopupMenuItem(
                  value: 'archive',
                  child: ListTile(
                    leading: Icon(Icons.archive_outlined),
                    title: Text('Archiver'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              const PopupMenuItem(
                value: 'refresh',
                child: ListTile(
                  leading: Icon(Icons.refresh_rounded),
                  title: Text('Actualiser'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ],
      ),
      body: _loading && doc == null
          ? const Center(child: CircularProgressIndicator.adaptive())
          : _error != null && doc == null
          ? Center(child: Text(_error!))
          : doc == null
          ? const Center(child: Text('Document indisponible.'))
          : RefreshIndicator(
              onRefresh: _load,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 760),
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(MakoloSpacing.inner),
                    children: [
                      ResourceDocumentHeader(
                        title: doc['title']?.toString() ?? 'Document',
                        subtitle: doc['visibility'] == 'restricted'
                            ? 'Confidentiel'
                            : 'Équipe autorisée',
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: MakoloSpacing.sm),
                        Text(
                          _error!,
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(
                                color: Theme.of(context)
                                    .colorScheme
                                    .onSurfaceVariant,
                              ),
                        ),
                      ],
                      const SizedBox(height: MakoloSpacing.lg),
                      if (currentVersion != null)
                        ResourceVersionCard(
                          leading: Icons.description_outlined,
                          title:
                              'Version ${currentVersion['number'] ?? doc['latest_version'] ?? 1}',
                          subtitle:
                              currentVersion['mime_type']?.toString() ??
                              'Document',
                          onTap: canPreview(currentVersion) && !_working
                              ? () => _preview(currentVersion)
                              : null,
                        ),
                      if (_canManage) ...[
                        const SizedBox(height: MakoloSpacing.md),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: MakoloActionButton(
                            label: 'Nouvelle version',
                            icon: Icons.add_rounded,
                            appearance: MakoloActionAppearance.quiet,
                            onPressed: _working ? null : _replace,
                          ),
                        ),
                      ],
                      if (previousVersions.isNotEmpty) ...[
                        const SizedBox(height: MakoloSpacing.xl),
                        ResourceSectionHeader(
                          title: 'Versions précédentes',
                          count: previousVersions.length,
                        ),
                        const SizedBox(height: MakoloSpacing.sm),
                        for (final version in previousVersions)
                          Padding(
                            padding: const EdgeInsets.only(
                              bottom: MakoloSpacing.sm,
                            ),
                            child: ResourceVersionCard(
                              title: 'v${version['number']}',
                              subtitle:
                                  version['mime_type']?.toString() ??
                                  'Document',
                              onTap: canPreview(version) && !_working
                                  ? () => _preview(version)
                                  : null,
                              actions: previousVersionActions(version),
                            ),
                          ),
                      ],
                      if (_canManage && _shares.isNotEmpty) ...[
                        const SizedBox(height: MakoloSpacing.xl),
                        ResourceSectionHeader(
                          title: 'Partages',
                          count: _shares.length,
                        ),
                        const SizedBox(height: MakoloSpacing.sm),
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
                ),
              ),
            ),
    );
  }
}

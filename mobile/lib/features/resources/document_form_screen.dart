import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;

import '../../data/files/profile_file_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../platform/files/system_file_picker.dart';
import 'resource_repository.dart';

class DocumentFormScreen extends StatefulWidget {
  const DocumentFormScreen.create({
    super.key,
    required this.repository,
    required this.onSaved,
    this.markFileId,
    this.markFileName,
  }) : assetId = null;

  const DocumentFormScreen.version({
    super.key,
    required this.repository,
    required String this.assetId,
    required this.onSaved,
  }) : markFileId = null,
       markFileName = null;

  final ResourceRepository repository;
  final String? assetId;
  final String? markFileId;
  final String? markFileName;
  final ValueChanged<String> onSaved;

  bool get isVersion => assetId != null;

  @override
  State<DocumentFormScreen> createState() => _DocumentFormScreenState();
}

class _DocumentFormScreenState extends State<DocumentFormScreen> {
  static const _extensions = [
    'pdf',
    'docx',
    'doc',
    'txt',
    'jpg',
    'jpeg',
    'png',
  ];

  final _title = TextEditingController();
  final _picker = const NativeSystemFilePicker();

  ResourceDocumentOptions _options = ResourceDocumentOptions.fallback;
  String _kind = 'other';
  String _sensitivity = 'normal';
  DateTime? _issuedAt;
  DateTime? _expiresAt;
  ProfileFileStore? _fileStore;
  StoredLocalFile? _file;
  String? _filename;
  bool _busy = false;
  bool _saved = false;
  bool _saveFailed = false;
  bool _loadingMarkFile = false;
  String? _prefillError;

  @override
  void initState() {
    super.initState();
    if (!widget.isVersion) {
      unawaited(_loadOptions());
      if (widget.markFileId != null) {
        unawaited(_loadMarkFile());
      }
    }
  }

  @override
  void dispose() {
    _title.dispose();
    final file = _file;
    final store = _fileStore;
    if (file != null && store != null) {
      unawaited(store.remove(file.fileId));
    }
    super.dispose();
  }

  Future<void> _loadOptions() async {
    final options = await widget.repository.documentOptions();
    if (!mounted) return;
    setState(() {
      _options = options;
      if (!_options.kinds.any((option) => option.id == _kind)) {
        _kind = _options.kinds.first.id;
      }
      if (!_options.sensitivities.any((option) => option.id == _sensitivity)) {
        _sensitivity = _options.sensitivities.first.id;
      }
    });
  }

  Future<ProfileFileStore> _store() async {
    final existing = _fileStore;
    if (existing != null) return existing;
    final opened = await ProfileFileStore.open(
      database: widget.repository.database,
      profileId: widget.repository.profileId,
    );
    _fileStore = opened;
    return opened;
  }

  Future<void> _pickFile() async {
    if (_busy || _loadingMarkFile) return;
    final picked = await _picker.pick(allowedExtensions: _extensions);
    if (!mounted || picked.isEmpty) return;
    final source = picked.first;
    final contentType = _contentType(source.name);
    if (contentType == null) {
      _message('Format non pris en charge.');
      return;
    }

    try {
      final store = await _store();
      final previous = _file;
      if (previous != null) await store.remove(previous.fileId);
      final id =
          'personal-asset-${widget.repository.profileId}-'
          '${DateTime.now().toUtc().microsecondsSinceEpoch}';
      final staged = await store.stageCopy(
        fileId: id,
        owner: 'PersonalAsset',
        sourceFilename: source.name,
        purpose: widget.isVersion
            ? 'personal_asset_version'
            : 'personal_asset_create',
        sensitivity: _sensitivity,
        writeTo: source.copyTo,
      );
      if (!mounted) {
        await store.remove(staged.fileId);
        return;
      }
      setState(() {
        _file = staged;
        _filename = source.name;
      });
    } on Object {
      if (mounted) _message('Impossible d’ajouter ce fichier.');
    }
  }

  Future<void> _loadMarkFile() async {
    final fileId = widget.markFileId;
    if (fileId == null || fileId.isEmpty || widget.isVersion) return;
    setState(() {
      _loadingMarkFile = true;
      _prefillError = null;
    });
    try {
      final store = await _store();
      final source = await store.read(fileId);
      if (source == null ||
          source.profileId != widget.repository.profileId ||
          source.owner != 'profile' ||
          source.purpose != 'mark_intake' ||
          !await File(source.path).exists()) {
        throw StateError('Mark file is unavailable in this Profile');
      }
      final suffix = p.extension(source.path).toLowerCase();
      final candidate = p.basename(widget.markFileName ?? '');
      final filename = p.extension(candidate).toLowerCase() == suffix &&
              _contentType(candidate) != null
          ? candidate
          : 'Document$suffix';
      if (_contentType(filename) == null) {
        throw StateError('Mark document format not supported by PersonalAsset');
      }

      // The owner form works with its own staged copy. Cancelling or failing
      // this form must never delete the original Mark draft attachment.
      final copy = await store.stageCopy(
        fileId:
            'personal-asset-mark-${widget.repository.profileId}-'
            '${DateTime.now().toUtc().microsecondsSinceEpoch}',
        owner: 'PersonalAsset',
        sourceFilename: filename,
        purpose: 'personal_asset_create',
        sensitivity: _sensitivity,
        writeTo: (destinationPath) async {
          await File(source.path).copy(destinationPath);
        },
      );
      if (!mounted) {
        await store.remove(copy.fileId);
        return;
      }
      setState(() {
        _file = copy;
        _filename = filename;
        if (_title.text.trim().isEmpty) {
          _title.text = p.basenameWithoutExtension(filename);
        }
      });
    } on Object {
      if (mounted) {
        setState(() => _prefillError =
            'Cette pièce n’est pas accessible depuis Mes documents. '
            'Vous pouvez choisir un autre fichier.');
      }
    } finally {
      if (mounted) setState(() => _loadingMarkFile = false);
    }
  }

  Future<void> _chooseDate({required bool expiry}) async {
    final initial = expiry ? _expiresAt : _issuedAt;
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: initial ?? now,
      firstDate: DateTime(1900),
      lastDate: DateTime(now.year + 50),
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (expiry) {
        _expiresAt = picked;
      } else {
        _issuedAt = picked;
      }
    });
  }

  Future<void> _submit() async {
    if (_busy || _saved || _loadingMarkFile) return;
    final file = _file;
    final filename = _filename;
    if (file == null || filename == null) {
      _message('Choisissez un fichier.');
      return;
    }
    if (!widget.isVersion && _title.text.trim().isEmpty) {
      _message('Ajoutez un titre.');
      return;
    }
    if (_issuedAt != null &&
        _expiresAt != null &&
        _expiresAt!.isBefore(_issuedAt!)) {
      _message('Vérifiez les dates.');
      return;
    }
    final contentType = _contentType(filename);
    if (contentType == null) {
      _message('Format non pris en charge.');
      return;
    }

    setState(() {
      _busy = true;
      _saveFailed = false;
    });
    try {
      final id = widget.isVersion
          ? await widget.repository.addDocumentVersionForAsset(
              assetId: widget.assetId!,
              filePath: file.path,
              filename: filename,
              contentType: contentType,
              issuedAt: _issuedAt,
              expiresAt: _expiresAt,
            )
          : await widget.repository.createDocument(
              title: _title.text,
              kind: _kind,
              sensitivity: _sensitivity,
              filePath: file.path,
              filename: filename,
              contentType: contentType,
              issuedAt: _issuedAt,
              expiresAt: _expiresAt,
            );

      // Once the owner confirms the new asset, cleanup errors are not
      // interpreted as another failed submission.
      if (mounted) setState(() => _saved = true);
      final store = _fileStore;
      if (store != null) {
        try {
          await store.remove(file.fileId);
        } on Object {
          // Cleanup is best-effort after the confirmed owner result.
        }
      }
      _file = null;
      _filename = null;
      if (!mounted) return;
      widget.onSaved(widget.isVersion ? widget.assetId! : id);
    } on Object {
      if (mounted && !_saved) {
        setState(() => _saveFailed = true);
        _message('Enregistrement non confirmé. Vérifiez avant de réessayer.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.isVersion ? 'Nouvelle version' : 'Nouveau document';
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Enregistrer',
            icon: Icons.check_rounded,
            onPressed: _busy || _saved || _loadingMarkFile ? null : _submit,
            phase: _busy
                ? MakoloActionPhase.processing
                : _saved
                ? MakoloActionPhase.confirmed
                : _saveFailed
                ? MakoloActionPhase.failed
                : MakoloActionPhase.available,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        children: [
          if (!widget.isVersion) ...[
            TextField(
              controller: _title,
              maxLength: 220,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Titre',
                prefixIcon: Icon(Icons.title_rounded),
              ),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            DropdownButtonFormField<String>(
              initialValue: _kind,
              decoration: const InputDecoration(
                labelText: 'Type',
                prefixIcon: Icon(Icons.description_outlined),
              ),
              items: [
                for (final option in _options.kinds)
                  DropdownMenuItem(value: option.id, child: Text(option.label)),
              ],
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value != null) setState(() => _kind = value);
                    },
            ),
            const SizedBox(height: MakoloSpacing.sm),
            DropdownButtonFormField<String>(
              initialValue: _sensitivity,
              decoration: const InputDecoration(
                labelText: 'Confidentialité',
                prefixIcon: Icon(Icons.shield_outlined),
              ),
              items: [
                for (final option in _options.sensitivities)
                  DropdownMenuItem(value: option.id, child: Text(option.label)),
              ],
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value != null) {
                        setState(() => _sensitivity = value);
                      }
                    },
            ),
            const SizedBox(height: MakoloSpacing.lg),
          ],
          if (_prefillError != null) ...[
            Text(
              _prefillError!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            const SizedBox(height: MakoloSpacing.sm),
          ],
          MakoloCard(
            onTap: _busy || _loadingMarkFile ? null : _pickFile,
            child: Row(
              children: [
                Icon(
                  _file == null
                      ? Icons.add_to_drive_outlined
                      : Icons.description_outlined,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: MakoloSpacing.md),
                Expanded(
                  child: Text(
                    _filename ?? 'Choisir un fichier',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                const Icon(Icons.chevron_right_rounded),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.lg),
          Row(
            children: [
              Expanded(
                child: _DateField(
                  label: 'Émission',
                  value: _issuedAt,
                  onTap: _busy ? null : () => _chooseDate(expiry: false),
                  onClear: _busy || _issuedAt == null
                      ? null
                      : () => setState(() => _issuedAt = null),
                ),
              ),
              const SizedBox(width: MakoloSpacing.sm),
              Expanded(
                child: _DateField(
                  label: 'Échéance',
                  value: _expiresAt,
                  onTap: _busy ? null : () => _chooseDate(expiry: true),
                  onClear: _busy || _expiresAt == null
                      ? null
                      : () => setState(() => _expiresAt = null),
                ),
              ),
            ],
          ),
          if (_busy || _loadingMarkFile) ...[
            const SizedBox(height: MakoloSpacing.lg),
            const LinearProgressIndicator(),
          ],
        ],
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({
    required this.label,
    required this.value,
    required this.onTap,
    required this.onClear,
  });

  final String label;
  final DateTime? value;
  final VoidCallback? onTap;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) => InkWell(
    borderRadius: BorderRadius.circular(16),
    onTap: onTap,
    child: InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: const Icon(Icons.calendar_month_outlined),
        suffixIcon: onClear == null
            ? null
            : IconButton(
                tooltip: 'Effacer',
                onPressed: onClear,
                icon: const Icon(Icons.close_rounded),
              ),
      ),
      child: Text(value == null ? '—' : _formatDate(value!)),
    ),
  );
}

String _formatDate(DateTime value) {
  final day = value.day.toString().padLeft(2, '0');
  final month = value.month.toString().padLeft(2, '0');
  return '$day/$month/${value.year}';
}

String? _contentType(String filename) => switch (p
    .extension(filename)
    .toLowerCase()) {
  '.pdf' => 'application/pdf',
  '.docx' =>
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.doc' => 'application/msword',
  '.txt' => 'text/plain',
  '.jpg' || '.jpeg' => 'image/jpeg',
  '.png' => 'image/png',
  _ => null,
};

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:pretty_qr_code/pretty_qr_code.dart';

import '../../design/makolo_theme.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../features/discovery/discovery_selector.dart';

/// The existing Discovery projection rendered as one N1 unit.
 /// Facts and actions remain owned by the server; this widget only composes.
class DiscoveryPossibilityUnit extends StatefulWidget {
  const DiscoveryPossibilityUnit({
    super.key,
    required this.item,
    required this.onOpen,
    this.onSave,
    this.allowSavePrompt = false,
    this.onSelect,
    this.selectionActionLabel,
    this.baseUri,
    this.compact = false,
  });

  final DiscoveryItemPresentation item;
  final VoidCallback onOpen;
  final Future<void> Function()? onSave;
  final bool allowSavePrompt;
  final VoidCallback? onSelect;
  final String? selectionActionLabel;
  final Uri? baseUri;
  final bool compact;

  @override
  State<DiscoveryPossibilityUnit> createState() => _DiscoveryPossibilityUnitState();
}

class _DiscoveryPossibilityUnitState extends State<DiscoveryPossibilityUnit> {
  bool _saving = false;

  static const _orbitAvailable = '''
<svg viewBox="0 0 24 24"><path d="M5.2 17.6A8.7 8.7 0 0 1 16.9 5.1" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/><path d="M18.4 7.2a8.6 8.6 0 0 1 .2 7.4" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/><circle cx="19.3" cy="17.6" r="1.45" fill="#000"/></svg>
''';
  static const _orbitSaved = '''
<svg viewBox="0 0 24 24"><path d="M5.6 17.2a8.2 8.2 0 1 1 12.9-1.4" fill="none" stroke="#000" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="12" r="3.2" fill="#000"/><circle cx="19.2" cy="17.5" r="1.55" fill="#000"/></svg>
''';

  static Widget orbitIcon({required bool saved, required Color color}) {
    return SvgPicture.string(
      saved ? _orbitSaved : _orbitAvailable,
      width: 21,
      height: 21,
      colorFilter: ColorFilter.mode(color, BlendMode.srcIn),
      semanticsLabel: saved ? 'Enregistré' : 'Enregistrer',
    );
  }

  Future<void> _save() async {
    if (_saving || widget.onSave == null) return;
    setState(() => _saving = true);
    try {
      await widget.onSave!();
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('L’enregistrement n’a pas pu être confirmé.')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Uri? get _shareableUrl {
    final raw = widget.item.links['web'];
    if (raw == null || raw.isEmpty || widget.baseUri == null) return null;
    final candidate = Uri.tryParse(raw);
    if (candidate == null) return null;
    final uri = widget.baseUri!.resolveUri(candidate);
    if (uri.scheme != 'https' && uri.scheme != 'http') return null;
    if (uri.host != widget.baseUri!.host || uri.port != widget.baseUri!.port) return null;
    if (uri.userInfo.isNotEmpty) return null;
    return uri;
  }

  DiscoveryItemPresentation get item => widget.item;

  List<Map<String, dynamic>> get _reliableFacts =>
      item.presentationFacts.where((fact) {
        final label = fact['label'];
        final value = fact['value'];
        return label is String &&
            label.trim().isNotEmpty &&
            value is String &&
            value.trim().isNotEmpty;
      }).take(6).toList(growable: false);

  String? get _documentLabel {
    for (final binding in item.mediaBindings) {
      final resource = binding['resource'];
      if (resource is! Map) continue;
      final mime = (resource['mime_type'] ?? binding['mime_type'] ?? '').toString().toLowerCase();
      final name = (resource['name'] ?? resource['title'] ?? '').toString().trim();
      final kind = mime.contains('pdf')
          ? 'PDF'
          : mime.contains('spreadsheet') || mime.contains('excel')
              ? 'Tableur'
              : mime.contains('document')
                  ? 'Document'
                  : null;
      if (kind != null) return name.isEmpty ? kind : '$kind · $name';
    }
    return null;
  }

  Widget _media(BuildContext context) {
    final uri = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    final validImage = uri != null &&
        (uri.scheme == 'https' || uri.scheme == 'http') &&
        uri.host.isNotEmpty;
    if (!validImage) return const SizedBox.shrink();
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: Image.network(
        item.imageUrl!,
        fit: BoxFit.cover,
        semanticLabel: 'Visuel de ${item.title}',
        errorBuilder: (_, _, _) => const SizedBox.shrink(),
      ),
    );
  }

  Widget _facts(BuildContext context) {
    final facts = _reliableFacts;
    if (facts.isEmpty) {
      final values = <String>[
        if (item.routeLabel != null) item.routeLabel!,
        if (item.timing != null) item.timing!,
        if (item.place != null) item.place!,
        if (item.price != null) item.price!,
        if (item.availability != null) item.availability!,
      ];
      if (values.isEmpty) return const SizedBox.shrink();
      return Wrap(
        spacing: MakoloSpacing.sm,
        runSpacing: MakoloSpacing.xs,
        children: [for (final value in values) Text(value, style: Theme.of(context).textTheme.bodySmall)],
      );
    }
    return Wrap(
      spacing: MakoloSpacing.md,
      runSpacing: MakoloSpacing.sm,
      children: [
        for (final fact in facts)
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  fact['label'] as String,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                Text(fact['value'] as String, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
      ],
    );
  }

  Widget _knowledge(BuildContext context) {
    final significant = item.assessment.where((fact) {
      return fact['state'] == 'limiting' || fact['state'] == 'unknown';
    }).take(2);
    if (significant.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final fact in significant)
          if (fact['label'] is String && (fact['label'] as String).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(
                fact['label'] as String,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
      ],
    );
  }

  Future<void> _share(BuildContext context, String action, Uri uri) async {
    try {
      if (action == 'copy') {
        await Clipboard.setData(ClipboardData(text: uri.toString()));
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Lien copié.')),
          );
        }
      } else if (action == 'external') {
        await const SystemShareGateway().shareText('${item.title}\n$uri');
      } else if (action == 'qr' && context.mounted) {
        await showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Partager par QR'),
            content: SizedBox(
              width: 220,
              height: 220,
              child: PrettyQrView.data(data: uri.toString()),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Fermer')),
            ],
          ),
        );
      }
    } on Object {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Le partage n’a pas pu aboutir.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final saved = item.savedState == 'saved';
    final canToggle = saved ? item.canUnsave : item.canSave;
    final url = _shareableUrl;
    final doc = _documentLabel;
    final focus = item.imageUrl != null;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (focus && !widget.compact) _media(context),
          InkWell(
            onTap: widget.onOpen,
            child: Padding(
              padding: EdgeInsets.all(widget.compact ? MakoloSpacing.sm : MakoloSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (item.eyebrow != null && item.eyebrow!.trim().isNotEmpty)
                    Text(item.eyebrow!, style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.primary)),
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(item.title, style: widget.compact ? theme.textTheme.titleSmall : theme.textTheme.titleMedium),
                  if (item.owner != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(item.owner!, style: theme.textTheme.labelMedium),
                  ],
                  if (item.summary.trim().isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(item.summary, style: widget.compact ? theme.textTheme.bodySmall : theme.textTheme.bodyMedium),
                  ],
                  if (doc != null) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Row(children: [
                      const Icon(Icons.description_outlined, size: 18),
                      const SizedBox(width: MakoloSpacing.xs),
                      Expanded(child: Text(doc, style: theme.textTheme.bodySmall)),
                    ]),
                  ],
                  const SizedBox(height: MakoloSpacing.md),
                  _facts(context),
                  _knowledge(context),
                  if (item.variants.isNotEmpty || item.relations.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      [
                        if (item.variants.isNotEmpty) '${item.variants.length} variantes',
                        if (item.relations.isNotEmpty) '${item.relations.length} relations',
                      ].join(' · '),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (!widget.compact) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: MakoloSpacing.xs, vertical: MakoloSpacing.xs),
              child: Row(
                children: [
                  Expanded(
                    child: TextButton(
                      onPressed: !_saving && widget.onSave != null && (canToggle || widget.allowSavePrompt) ? _save : null,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            orbitIcon(saved: saved, color: theme.colorScheme.primary),
                            const SizedBox(height: 3),
                            Text(_saving ? 'Enregistrement…' : saved ? 'Enregistré' : 'J’enregistre'),
                          ],
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    child: TextButton(
                      onPressed: widget.onOpen,
                      child: const Text('Voir plus', textAlign: TextAlign.center),
                    ),
                  ),
                  Expanded(
                    child: url == null
                        ? const SizedBox.shrink()
                        : PopupMenuButton<String>(
                            tooltip: 'Partager',
                            onSelected: (value) => _share(context, value, url),
                            itemBuilder: (context) => const [
                              PopupMenuItem(value: 'external', child: Text('Partager avec…')),
                              PopupMenuItem(value: 'copy', child: Text('Copier le lien')),
                              PopupMenuItem(value: 'qr', child: Text('Afficher le QR')),
                            ],
                            child: const Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.share_outlined),
                                SizedBox(height: 3),
                                Text('Partager'),
                              ],
                            ),
                          ),
                  ),
                ],
              ),
            ),
          ],
          if (widget.onSelect != null)
            TextButton.icon(
              onPressed: widget.onSelect,
              icon: const Icon(Icons.map_outlined),
              label: Text(widget.selectionActionLabel ?? 'Voir sur la carte'),
            ),
        ],
      ),
    );
  }
}

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';

/// C2_bus: presentation only. The owner still controls who can see a Point,
/// reply, download media, and whether a response has been confirmed.
class ConversationPointShell extends StatelessWidget {
  const ConversationPointShell({
    super.key,
    required this.kind,
    required this.isMine,
    required this.child,
    this.authorLabel,
    this.representedSpace = false,
    this.representedSpaceLabel,
    this.publishedAt,
    this.statusIcon,
  });

  final String kind;
  final bool isMine;
  final String? authorLabel;
  final bool representedSpace;

  /// Canonical Space context label; it is not an author's name or a role.
  final String? representedSpaceLabel;
  final DateTime? publishedAt;
  final Widget? statusIcon;
  final Widget child;

  static (String, IconData) typePresentation(String kind) => switch (kind) {
    'question' => ('Question', Icons.help_outline_rounded),
    'request' => ('Demande', Icons.assignment_outlined),
    'form_request' => ('Formulaire', Icons.article_outlined),
    'poll' => ('Sondage', Icons.poll_outlined),
    'confirmation' => ('Confirmation', Icons.task_alt_rounded),
    'exchange' => ('Échange', Icons.forum_outlined),
    'information' => ('Information', Icons.chat_bubble_outline_rounded),
    _ => ('Point', Icons.chat_bubble_outline_rounded),
  };

  String get _identity {
    if (isMine) return 'Vous';
    final value = authorLabel?.trim();
    return value == null || value.isEmpty ? 'Participant' : value;
  }

  String get _initials {
    final words = _identity.replaceAll('·', ' ').trim().split(RegExp(r'\s+'));
    if (words.isEmpty) return '?';
    return words
        .where((part) => part.isNotEmpty)
        .take(2)
        .map((part) => part.substring(0, 1))
        .join()
        .toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context).textTheme;
    final (label, typeIcon) = typePresentation(kind);
    final isOrdinary = kind == 'information';
    final timestamp = publishedAt?.toLocal();
    final time = timestamp == null
        ? null
        : MaterialLocalizations.of(context).formatTimeOfDay(
            TimeOfDay.fromDateTime(timestamp),
            alwaysUse24HourFormat: true,
          );

    return LayoutBuilder(
      builder: (context, constraints) {
        final maxWidth = math.min(constraints.maxWidth * 0.94, 600.0);
        final background = isMine
            ? Color.alphaBlend(
                scheme.primary.withValues(alpha: 0.08),
                scheme.surface,
              )
            : scheme.surface;
        return Align(
          alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: background,
                border: Border.all(
                  color: isMine
                      ? scheme.primary.withValues(alpha: 0.14)
                      : scheme.outlineVariant.withValues(alpha: 0.6),
                ),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: Radius.circular(isMine ? 18 : 5),
                  bottomRight: Radius.circular(isMine ? 5 : 18),
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.compact,
                  vertical: MakoloSpacing.compact,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 13,
                          backgroundColor: isMine
                              ? scheme.primary.withValues(alpha: 0.14)
                              : scheme.surfaceContainerHighest,
                          child: Text(
                            _initials,
                            style: theme.labelSmall?.copyWith(
                              color: isMine ? scheme.primary : scheme.onSurface,
                              fontSize: 10,
                            ),
                          ),
                        ),
                        const SizedBox(width: 7),
                        Flexible(
                          child: Text(
                            _identity,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.labelMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        if (representedSpace && !isMine) ...[
                          const SizedBox(width: 4),
                          Icon(
                            Icons.business_outlined,
                            size: 14,
                            color: scheme.onSurfaceVariant,
                          ),
                        ],
                      ],
                    ),
                    if (representedSpace &&
                        representedSpaceLabel != null &&
                        representedSpaceLabel!.trim().isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        'Dans le cadre de ${representedSpaceLabel!}',
                        style: theme.labelSmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    if (!isOrdinary) ...[
                      const SizedBox(height: 10),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(typeIcon, size: 15, color: scheme.primary),
                          const SizedBox(width: 5),
                          Text(
                            label,
                            style: theme.labelSmall?.copyWith(
                              color: scheme.primary,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 9),
                    child,
                    if (time != null || statusIcon != null) ...[
                      const SizedBox(height: 5),
                      Align(
                        alignment: Alignment.bottomRight,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (time != null)
                              Text(
                                time,
                                style: theme.labelSmall?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                ),
                              ),
                            if (statusIcon != null) ...[
                              const SizedBox(width: 5),
                              statusIcon!,
                            ],
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// A private media entry. Inline controls remain independently interactive;
/// opening the detail viewer is always a separate explicit action.
class ConversationPointMediaTile extends StatelessWidget {
  const ConversationPointMediaTile({
    super.key,
    required this.attachment,
    required this.onOpen,
    this.preview,
  });

  final Map<String, dynamic> attachment;
  final VoidCallback? onOpen;
  final Widget? preview;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context).textTheme;
    final kind = attachment['kind']?.toString() ?? 'file';
    final mime = attachment['mime_type']?.toString() ?? '';
    final (IconData icon, String title) = switch (kind) {
      'image' => (Icons.image_outlined, 'Photo'),
      'video' => (Icons.play_circle_outline_rounded, 'Vidéo'),
      'voice' => (Icons.graphic_eq_rounded, 'Note vocale'),
      'audio' => (Icons.headphones_outlined, 'Audio'),
      _ when mime == 'application/pdf' => (
        Icons.picture_as_pdf_outlined,
        'Document PDF',
      ),
      _ => (Icons.insert_drive_file_outlined, 'Document'),
    };
    final caption = attachment['caption']?.toString().trim();
    return Padding(
      padding: const EdgeInsets.only(top: MakoloSpacing.sm),
      child: Material(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (preview != null)
                preview!
              else
                Row(
                  children: [
                    Icon(icon, color: scheme.primary, size: 28),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(child: Text(title, style: theme.labelMedium)),
                  ],
                ),
              if (caption != null && caption.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 5),
                  child: Text(caption, style: theme.bodySmall),
                ),
              if (onOpen != null)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: onOpen,
                    icon: const Icon(Icons.open_in_full_rounded, size: 17),
                    label: Text(preview == null ? 'Ouvrir' : 'Voir en détail'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

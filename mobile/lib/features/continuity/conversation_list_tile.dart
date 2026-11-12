import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../presentation/humanization.dart';

/// A compact, recognizable Conversation entry. This is not a chat-message row:
/// counts indicate actionable Points, and media icons describe owned content.
class ConversationListTile extends StatelessWidget {
  const ConversationListTile({
    super.key,
    required this.title,
    required this.contextKind,
    required this.onTap,
    this.subtitle,
    this.preview,
    this.previewKind,
    this.mediaKinds = const [],
    this.publicImageUri,
    this.updatedAt,
    this.attentionCount = 0,
    this.unreadCount = 0,
    this.archived = false,
  });

  final String title;
  final String contextKind;
  final String? subtitle;
  final String? preview;
  final String? previewKind;
  final List<String> mediaKinds;
  final Uri? publicImageUri;
  final DateTime? updatedAt;
  final int attentionCount;
  final int unreadCount;
  final bool archived;
  final VoidCallback onTap;

  static IconData contextIcon(String kind) => switch (kind) {
    'direct' => Icons.person_rounded,
    'space' => Icons.business_rounded,
    'group' => Icons.groups_rounded,
    'activity' => Icons.local_activity_rounded,
    'occurrence' => Icons.event_available_rounded,
    'journey' => Icons.route_rounded,
    'dossier' => Icons.folder_copy_rounded,
    'project' => Icons.dashboard_customize_rounded,
    'action_proposal' => Icons.lightbulb_outline_rounded,
    _ => Icons.forum_rounded,
  };

  static IconData mediaIcon(String kind) => switch (kind) {
    'voice' => Icons.mic_rounded,
    'audio' => Icons.audiotrack_rounded,
    'image' => Icons.image_rounded,
    'video' => Icons.videocam_rounded,
    'file' => Icons.attach_file_rounded,
    'poll' => Icons.poll_rounded,
    'form' => Icons.assignment_rounded,
    'confirmation' => Icons.check_circle_outline_rounded,
    'exchange' => Icons.forum_outlined,
    _ => Icons.insert_drive_file_outlined,
  };

  static String mediaLabel(String kind) => switch (kind) {
    'voice' => 'Vocal',
    'audio' => 'Audio',
    'image' => 'Photo',
    'video' => 'Vidéo',
    'file' => 'Document',
    'poll' => 'Sondage',
    'form' => 'Formulaire',
    'confirmation' => 'Confirmation',
    'exchange' => 'Échanges',
    _ => 'Contenu',
  };

  String? _timeLabel() {
    final date = updatedAt;
    if (date == null) return null;
    final local = date.toLocal();
    final now = DateTime.now();
    if (local.year == now.year &&
        local.month == now.month &&
        local.day == now.day) {
      return MakoloHumanization.formatTime(date);
    }
    return MakoloHumanization.formatDay(date, now: now);
  }

  Widget _visual(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final fallback = Container(
      width: 56,
      height: 56,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: colors.primary.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(MakoloRadii.card),
      ),
      child: Icon(contextIcon(contextKind), size: 27, color: colors.primary),
    );
    final uri = publicImageUri;
    if (uri == null) return fallback;
    return ClipRRect(
      borderRadius: BorderRadius.circular(MakoloRadii.card),
      child: Image.network(
        uri.toString(),
        width: 56,
        height: 56,
        fit: BoxFit.cover,
        excludeFromSemantics: true,
        errorBuilder: (_, _, _) => fallback,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final time = _timeLabel();
    final summary = preview?.trim() ?? '';
    final detail = subtitle?.trim() ?? '';
    final visibleKinds = mediaKinds.take(4).toList(growable: false);
    final semanticLabel = [
      title,
      if (detail.isNotEmpty) detail,
      if (attentionCount > 0) '$attentionCount à traiter',
      if (unreadCount > 0) '$unreadCount messages non lus',
      if (summary.isNotEmpty) summary,
      if (visibleKinds.isNotEmpty)
        'Contenus : ${visibleKinds.map(mediaLabel).join(", ")}',
      if (archived) 'Archivée',
    ].join('. ');

    return Semantics(
      button: true,
      label: semanticLabel,
      hint: 'Ouvrir la Conversation',
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(MakoloRadii.medium),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              vertical: MakoloSpacing.compact,
              horizontal: MakoloSpacing.xs,
            ),
            child: ExcludeSemantics(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _visual(context),
                  const SizedBox(width: MakoloSpacing.compact),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                            height: 1.2,
                            color: colors.onSurface,
                          ),
                        ),
                        if (detail.isNotEmpty) ...[
                          const SizedBox(height: 3),
                          Text(
                            detail,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                        ],
                        if (summary.isNotEmpty) ...[
                          const SizedBox(height: 7),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (previewKind == 'result') ...[
                                Icon(
                                  Icons.check_circle_outline_rounded,
                                  size: 17,
                                  color: MakoloColors.success,
                                ),
                                const SizedBox(width: 5),
                              ],
                              Expanded(
                                child: Text(
                                  summary,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.bodyMedium?.copyWith(
                                    color: colors.onSurfaceVariant,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                        if (visibleKinds.isNotEmpty) ...[
                          const SizedBox(height: 7),
                          Wrap(
                            spacing: MakoloSpacing.compact,
                            runSpacing: MakoloSpacing.xs,
                            children: [
                              for (final kind in visibleKinds)
                                Tooltip(
                                  message: mediaLabel(kind),
                                  child: Icon(
                                    mediaIcon(kind),
                                    size: 17,
                                    color: colors.onSurfaceVariant,
                                  ),
                                ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(width: MakoloSpacing.xs),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 72),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        if (time != null)
                          Text(
                            time,
                            textAlign: TextAlign.end,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                        if (unreadCount > 0)
                          Padding(
                            padding: const EdgeInsets.only(top: 6),
                            child: Badge(label: Text('$unreadCount non lus')),
                          ),
                        if (attentionCount > 0) ...[
                          const SizedBox(height: 8),
                          DecoratedBox(
                            decoration: BoxDecoration(
                              color: colors.primary,
                              borderRadius: BorderRadius.circular(
                                MakoloRadii.pill,
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              child: Text(
                                '$attentionCount à faire',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: colors.onPrimary,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ),
                        ],
                        if (time == null && attentionCount == 0)
                          Padding(
                            padding: const EdgeInsets.only(top: 14),
                            child: Icon(
                              Icons.chevron_right_rounded,
                              size: 19,
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

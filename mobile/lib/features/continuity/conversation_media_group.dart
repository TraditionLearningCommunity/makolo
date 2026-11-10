import 'package:flutter/material.dart';

import 'conversation_attachment_viewer.dart';
import 'conversation_point_presentation.dart';
import 'conversation_repository.dart';

/// Group private attachments by their owning Point. Photos are a compact
/// gallery; audio, PDF and text are readable inline on explicit interaction.
/// No media URL or client-side authorization is manufactured here.
class ConversationMediaGroup extends StatefulWidget {
  const ConversationMediaGroup({
    super.key,
    this.repository,
    this.download,
    required this.attachments,
  });

  final ConversationRepository? repository;
  final PrivateMediaDownloader? download;
  final List<Map<String, dynamic>> attachments;

  @override
  State<ConversationMediaGroup> createState() => _ConversationMediaGroupState();
}

class _ConversationMediaGroupState extends State<ConversationMediaGroup> {
  bool _opening = false;

  Future<void> _open(BuildContext context, int index) async {
    if (_opening) return;
    _opening = true;
    try {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (_) => FractionallySizedBox(
        heightFactor: .92,
        child: ConversationAttachmentViewer(
          repository: widget.repository,
          download: widget.download,
          attachment: widget.attachments[index],
          gallery: widget.attachments,
          initialIndex: index,
        ),
      ),
    );
    } finally {
      _opening = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final attachments = widget.attachments;
    final repository = widget.repository;
    final download = widget.download;
    if (attachments.isEmpty) return const SizedBox.shrink();
    final visual = <int>[];
    final other = <int>[];
    for (var index = 0; index < attachments.length; index++) {
      final kind = attachments[index]['kind']?.toString();
      if (kind == 'image' || kind == 'video') {
        visual.add(index);
      } else {
        other.add(index);
      }
    }

    Widget visualTile(int index, {bool compact = false}) {
      final attachment = attachments[index];
      final image = attachment['kind'] == 'image';
      final caption = attachment['caption']?.toString().trim() ?? '';
      return Material(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => _open(context, index),
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (image)
                IgnorePointer(
                  child: ConversationAttachmentViewer(
                    key: ValueKey(
                      'conversation-inline-image-${attachment['id']?.toString() ?? index}',
                    ),
                    repository: repository,
                    download: download,
                    attachment: attachment,
                    inline: true,
                  ),
                )
              else
                Icon(
                  Icons.play_circle_outline_rounded,
                  size: compact ? 34 : 52,
                  color: Theme.of(context).colorScheme.primary,
                ),
              if (!image || caption.isNotEmpty)
                Align(
                  alignment: Alignment.bottomCenter,
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                      vertical: 7,
                      horizontal: 9,
                    ),
                    color: Colors.black54,
                    child: Text(
                      caption.isNotEmpty ? caption : 'Vidéo',
                      maxLines: compact ? 2 : 3,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (attachments.length > 1)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                '${attachments.length} médias associés',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ),
          if (visual.length == 1 &&
              attachments[visual.single]['kind'] == 'image')
            SizedBox(height: 206, child: visualTile(visual.single)),
          if (visual.length == 1 &&
              attachments[visual.single]['kind'] == 'video')
            ConversationPointMediaTile(
              attachment: attachments[visual.single],
              onOpen: () => _open(context, visual.single),
              preview: ConversationAttachmentViewer(
                repository: repository,
                download: download,
                attachment: attachments[visual.single],
                inline: true,
              ),
            ),
          if (visual.length > 1)
            LayoutBuilder(
              builder: (context, constraints) => GridView.builder(
                physics: const NeverScrollableScrollPhysics(),
                shrinkWrap: true,
                itemCount: visual.length > 4 ? 4 : visual.length,
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: constraints.maxWidth < 220 ? 1 : 2,
                  crossAxisSpacing: 4,
                  mainAxisSpacing: 4,
                  mainAxisExtent: constraints.maxWidth < 220
                      ? 148
                      : ((constraints.maxWidth - 4) / 2 / 1.35)
                          .clamp(112.0, 180.0).toDouble(),
                ),
                itemBuilder: (context, cell) {
                  final index = visual[cell];
                  final remaining = visual.length - 3;
                  return Stack(
                    fit: StackFit.expand,
                    children: [
                      visualTile(index, compact: true),
                      if (cell == 3 && remaining > 1)
                        IgnorePointer(
                          child: Container(
                            decoration: BoxDecoration(
                              color: Colors.black54,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              '+$remaining',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 25,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
          for (final index in other)
            ConversationPointMediaTile(
              key: ValueKey(
                'conversation-inline-file-${attachments[index]['id']?.toString() ?? index}',
              ),
              attachment: attachments[index],
              onOpen: () => _open(context, index),
              preview: ConversationAttachmentViewer(
                repository: repository,
                download: download,
                attachment: attachments[index],
                inline: true,
              ),
            ),
        ],
      ),
    );
  }
}

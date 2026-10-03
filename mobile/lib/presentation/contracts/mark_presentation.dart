import '../../design/surface_states.dart';
import '../../navigation/destination.dart';

class MarkAttachmentPresentation {
  const MarkAttachmentPresentation({
    required this.id,
    required this.name,
    this.mediaRef,
  });

  final String id;
  final String name;
  final String? mediaRef;
}

class MarkIntentPresentation {
  const MarkIntentPresentation({required this.label, this.consequence});

  final String label;
  final String? consequence;
}

class MarkPresentationInput {
  const MarkPresentationInput({
    required this.text,
    required this.draftCommit,
    required this.authority,
    this.attachments = const [],
    this.clarification,
    this.interpretation,
    this.consequence,
    this.intents = const [],
    this.actorContextLabel,
    this.handoff,
  });

  final String text;
  final List<MarkAttachmentPresentation> attachments;
  final MakoloCommitCue draftCommit;
  final MakoloAuthorityCue authority;
  final String? clarification;
  final String? interpretation;
  final String? consequence;
  final List<MarkIntentPresentation> intents;
  final String? actorContextLabel;
  final StructuredDestination? handoff;
}

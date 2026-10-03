import '../../design/surface_states.dart';
import '../../navigation/destination.dart';

class OngoingContinuityPresentation {
  const OngoingContinuityPresentation({
    required this.reference,
    required this.title,
    required this.currentSynthesis,
    required this.ownerDestination,
    this.settled = const [],
    this.mySide = const [],
    this.elsewhere = const [],
    this.next = const [],
    this.blocker,
    this.timing,
    this.place,
    this.mediaRef,
    this.freshness = MakoloFreshnessCue.unknown,
  });

  final StructuredDestination reference;
  final String title;
  final String currentSynthesis;
  final List<String> settled;
  final List<String> mySide;
  final List<String> elsewhere;
  final List<String> next;
  final String? blocker;
  final String? timing;
  final String? place;
  final String? mediaRef;
  final MakoloFreshnessCue freshness;
  final StructuredDestination ownerDestination;
}

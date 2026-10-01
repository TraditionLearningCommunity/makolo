import '../app/environment.dart';
import '../observability/observability.dart';
import '../platform/notifications/local_notification_scheduler.dart';
import '../platform/notifications/push_destination.dart';
import '../platform/notifications/push_signal.dart';
import 'firebase_runtime_bootstrap.dart';
import 'observability_bootstrap.dart';
import 'runtime_ingress.dart';
import 'runtime_service_status.dart';

class MakoloRuntimeServices {
  const MakoloRuntimeServices({
    required this.firebase,
    required this.observability,
    required this.crashReporter,
  });

  final RuntimeServiceStatus firebase;
  final RuntimeServiceStatus observability;
  final CrashReporter crashReporter;
}

class MakoloRuntimeBootstrap {
  MakoloRuntimeBootstrap({
    FirebaseRuntimeBootstrap? firebase,
    ObservabilityRuntime? observability,
    LocalNotificationScheduler? notifications,
  }) : firebase = firebase ?? FirebaseRuntimeBootstrap(),
       observability = observability ?? ObservabilityRuntime(),
       notifications = notifications ?? FlutterLocalNotificationScheduler();

  final FirebaseRuntimeBootstrap firebase;
  final ObservabilityRuntime observability;
  final LocalNotificationScheduler notifications;

  Future<MakoloRuntimeServices> initialize(
    MakoloRuntimeConfig config, {
    RuntimeIngress? ingress,
  }) async {
    final observabilityStatus = await observability.initialize(config);
    if (ingress != null) {
      try {
        await notifications.initialize(onIntent: ingress.add);
      } catch (error, stackTrace) {
        await observability.reporter.report(
          error,
          stackTrace,
          tags: const {'service': 'local_notifications', 'phase': 'initialize'},
        );
      }
    }
    final firebaseStatus = await firebase.initialize(config);
    if (ingress != null &&
        firebaseStatus.isReady &&
        firebase.messaging != null) {
      final receiver = FirebasePushSignalReceiver(
        messaging: firebase.messaging!,
      );
      const destinations = PushDestinationResolver();
      receiver.openedSignals.listen((signal) {
        final intent = destinations.intent(signal);
        if (intent != null) ingress.add(intent);
      });
      final initial = await receiver.initialSignal();
      if (initial != null) {
        final intent = destinations.intent(initial);
        if (intent != null) ingress.add(intent);
      }
    }
    return MakoloRuntimeServices(
      firebase: firebaseStatus,
      observability: observabilityStatus,
      crashReporter: observability.reporter,
    );
  }
}

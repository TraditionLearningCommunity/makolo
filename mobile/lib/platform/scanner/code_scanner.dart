import 'package:flutter/widgets.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../navigation/incoming_intent.dart';
import '../../navigation/structured_destination_codec.dart';

class ScannedCode {
  const ScannedCode({required this.value, this.format});

  final String value;
  final String? format;
}

class ScannedCodeIngress {
  const ScannedCodeIngress({this.codec = const StructuredDestinationCodec()});

  final StructuredDestinationCodec codec;

  IncomingIntent? navigationIntent(ScannedCode code) {
    final destination = codec.fromJson(code.value);
    if (destination == null) return null;
    return IncomingIntent(
      source: IncomingIntentSource.qr,
      destination: destination,
    );
  }
}

class MakoloCodeScanner extends StatelessWidget {
  const MakoloCodeScanner({required this.onCode, super.key});

  final ValueChanged<ScannedCode> onCode;

  @override
  Widget build(BuildContext context) {
    return MobileScanner(
      onDetect: (capture) {
        for (final barcode in capture.barcodes) {
          final value = barcode.rawValue;
          if (value == null || value.isEmpty) continue;
          onCode(ScannedCode(value: value, format: barcode.format.name));
          break;
        }
      },
    );
  }
}

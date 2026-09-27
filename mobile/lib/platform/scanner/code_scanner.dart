import 'package:flutter/widgets.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannedCode {
  const ScannedCode({required this.value, this.format});

  final String value;
  final String? format;
}

class MakoloCodeScanner extends StatelessWidget {
  const MakoloCodeScanner({required this.onCode, this.controller, super.key});

  final ValueChanged<ScannedCode> onCode;
  final MobileScannerController? controller;

  @override
  Widget build(BuildContext context) {
    return MobileScanner(
      controller: controller,
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

import 'package:flutter/widgets.dart';
import 'package:flutter_svg/flutter_svg.dart';

enum MakoloMarkSemantics { informative, structural, decorative }

class MakoloMark extends StatelessWidget {
  const MakoloMark({
    super.key,
    this.size = 36,
    this.white = false,
    this.semantics = MakoloMarkSemantics.informative,
  });

  final double size;
  final bool white;
  final MakoloMarkSemantics semantics;

  @override
  Widget build(BuildContext context) {
    final mark = SvgPicture.asset(
      white
          ? 'assets/brand/makolo-mark-white.svg'
          : 'assets/brand/makolo-mark-violet.svg',
      width: size,
      height: size,
      fit: BoxFit.contain,
      excludeFromSemantics: true,
    );

    return switch (semantics) {
      MakoloMarkSemantics.decorative => ExcludeSemantics(child: mark),
      MakoloMarkSemantics.informative => Semantics(
        label: 'Makolo',
        image: true,
        child: mark,
      ),
      MakoloMarkSemantics.structural => Semantics(
        container: true,
        label: 'Makolo',
        image: true,
        child: mark,
      ),
    };
  }
}

import java.util.Random;

/**
 * plijava runtime helper - random number generator for RANDOM() built-in.
 */
public class RndRuntime {
    private static final Random random = new Random();

    public static int random() {
        return random.nextInt(100) + 1;
    }

    public static int random(int kern) {
        return random.nextInt(kern) + 1;
    }

    public static int random(int kern, int dummy) {
        return random.nextInt(kern) + 1;
    }
}

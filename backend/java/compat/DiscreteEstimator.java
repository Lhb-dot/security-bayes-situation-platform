package weka.estimators;

/**
 * Weka compatibility extension required by the supplied CAVWNB sources.
 * It preserves the public 3.8 DiscreteEstimator API and adds the historical
 * Laplace-probability method used by WANBDistribution.
 */
public class DiscreteEstimator extends Estimator
        implements IncrementalEstimator, weka.core.Aggregateable<DiscreteEstimator> {
    private static final long serialVersionUID = 1L;

    private double[] counts;
    private double sum;

    public DiscreteEstimator() { this(1, false); }

    public DiscreteEstimator(int numSymbols, boolean laplace) {
        if (numSymbols < 1) throw new IllegalArgumentException("numSymbols must be positive");
        counts = new double[numSymbols];
        if (laplace) {
            for (int i = 0; i < counts.length; i++) counts[i] = 1.0;
            sum = counts.length;
        }
    }

    public DiscreteEstimator(int numSymbols, double alpha) {
        if (numSymbols < 1) throw new IllegalArgumentException("numSymbols must be positive");
        counts = new double[numSymbols];
        for (int i = 0; i < counts.length; i++) counts[i] = alpha;
        sum = alpha * counts.length;
    }

    @Override
    public void addValue(double data, double weight) {
        int index = (int) data;
        if (index < 0 || index >= counts.length) throw new IllegalArgumentException("invalid symbol: " + data);
        counts[index] += weight;
        sum += weight;
    }

    @Override
    public double getProbability(double data) {
        int index = (int) data;
        if (index < 0 || index >= counts.length || sum == 0.0) return 0.0;
        return counts[index] / sum;
    }

    public double getProbability_laplace(int data) {
        int index = (int) data;
        if (index < 0 || index >= counts.length) return 0.0;
        return (counts[index] + 1.0) / (sum + counts.length);
    }

    public int getNumSymbols() { return counts.length; }
    public double getCount(double data) { return counts[(int) data]; }
    public double getSumOfCounts() { return sum; }

    @Override
    public DiscreteEstimator aggregate(DiscreteEstimator other) throws Exception {
        if (other == null || other.counts.length != counts.length) throw new Exception("incompatible estimators");
        DiscreteEstimator result = new DiscreteEstimator(counts.length, 0.0);
        for (int i = 0; i < counts.length; i++) result.counts[i] = counts[i] + other.counts[i];
        result.sum = sum + other.sum;
        return result;
    }

    @Override
    public void finalizeAggregation() { }
}

package lbfgsb;

import java.util.ArrayList;
import java.util.List;

/**
 * Pure-Java bounded optimizer compatible with the supplied CAVWNB API.
 * It avoids the optional native lbfgsb_wrapper library while preserving the
 * actual CAVWNB objective and gradient supplied by the algorithm.
 */
public class Minimizer {
    private final StopConditions stopConditions = new StopConditions();
    private List<Bound> bounds = new ArrayList<>();

    public Minimizer() { }
    public StopConditions getStopConditions() { return stopConditions; }
    public List<Bound> getBounds() { return bounds; }
    public void setBounds(List<Bound> value) { bounds = value == null ? new ArrayList<>() : value; }
    public int getCorrectionsNo() { return 0; }
    public void setCorrectionsNo(int value) { }
    public void setNoBounds(int value) { }
    public void setIterationFinishedListener(Object value) { }
    public int getDebugLevel() { return 0; }
    public void setDebugLevel(int value) { }

    public Result run(DifferentiableFunction function, double[] startingPoint) throws LBFGSBException {
        if (function == null || startingPoint == null) throw new LBFGSBException("缺少优化目标");
        double[] point = startingPoint.clone();
        FunctionValues current = function.getValues(point);
        if (current == null || current.gradient == null) throw new LBFGSBException("优化目标未返回梯度");
        double step = 0.1;
        for (int iteration = 0; iteration < stopConditions.getMaxIterations(); iteration++) {
            double norm = norm(current.gradient);
            if (norm <= stopConditions.getMaxGradientNorm()) break;
            double[] candidate = point.clone();
            for (int i = 0; i < candidate.length; i++) {
                candidate[i] -= step * current.gradient[i];
                if (i < bounds.size() && bounds.get(i) != null) {
                    Bound bound = bounds.get(i);
                    if (bound.lowerBound != null) candidate[i] = Math.max(candidate[i], bound.lowerBound);
                    if (bound.upperBound != null) candidate[i] = Math.min(candidate[i], bound.upperBound);
                }
            }
            FunctionValues next = function.getValues(candidate);
            if (next != null && next.functionValue <= current.functionValue) {
                point = candidate;
                current = next;
                step = Math.min(0.2, step * 1.05);
            } else {
                step *= 0.5;
                if (step < 1e-10) break;
            }
        }
        return new Result(point, current.functionValue, current.gradient, new IterationsInfo());
    }

    private static double norm(double[] values) {
        double sum = 0.0;
        for (double value : values) sum += value * value;
        return Math.sqrt(sum);
    }
}

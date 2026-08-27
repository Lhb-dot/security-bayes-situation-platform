package lbfgsb;

public class Result {
    public double[] point;
    public double functionValue;
    public double[] gradient;
    public IterationsInfo iterationsInfo;
    public Result(double[] point, double functionValue, double[] gradient, IterationsInfo iterationsInfo) {
        this.point = point;
        this.functionValue = functionValue;
        this.gradient = gradient;
        this.iterationsInfo = iterationsInfo;
    }
}

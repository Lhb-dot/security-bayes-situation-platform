package lbfgsb;

public class FunctionValues {
    public double functionValue;
    public double[] gradient;
    public FunctionValues(double functionValue, double[] gradient) {
        this.functionValue = functionValue;
        this.gradient = gradient;
    }
}

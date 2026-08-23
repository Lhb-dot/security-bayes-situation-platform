package lbfgsb;

public class StopConditions {
    private double functionReductionFactor = 1e-9;
    private double maxGradientNorm = 1e-5;
    private int maxIterations = 200;
    public double getFunctionReductionFactor() { return functionReductionFactor; }
    public void setFunctionReductionFactor(double value) { functionReductionFactor = value; }
    public boolean isFunctionReductionFactorActive() { return true; }
    public void setFunctionReductionFactorInactive() { }
    public double getMaxGradientNorm() { return maxGradientNorm; }
    public void setMaxGradientNorm(double value) { maxGradientNorm = value; }
    public boolean isMaxGradientNormActive() { return true; }
    public void setMaxGradientNormInactive() { }
    public int getMaxIterations() { return maxIterations; }
    public void setMaxIterations(int value) { maxIterations = Math.max(1, value); }
    public boolean isMaxIterationsActive() { return true; }
    public void setMaxIterationsInactive() { }
}

def plot(x,y, **kwargs):
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Qt5Agg')
    plt.plot(x,y, **kwargs)
    plt.show()

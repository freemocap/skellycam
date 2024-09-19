import type {Configuration} from 'webpack';

import {rules} from './webpack.rules';
import {plugins} from './webpack.plugins';

rules.push({
    test: /\.css$/,
    use: [{loader: 'style-loader'}, {loader: 'css-loader'}],
});

rules.push({
    test: /\.tsx?$/,
    exclude: /node_modules/,
    use: {
        loader: 'ts-loader',
        options: {
            transpileOnly: true,
        },
    },
});

export const rendererConfig: Configuration = {
    entry: './src/index.tsx',
    module: {
        rules,
    },
    plugins,
    resolve: {
        extensions: ['.js', '.ts', '.jsx', '.tsx', '.css'],
    },
};

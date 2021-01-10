# Community Strategies

This repository contains community-created strategies for the Python Strategy Editor of the margin
application found at [margin.io]().

This package is available for Python 3.6 or higher through pip
```
pip install margin-community-strategies
```

If you want to write your own strategies, we recommend installing the strategy SDK from
https://github.com/MarginOpenSource/strategy-sdk or using pip
```
pip install margin-strategy-sdk
```
and start by cloning the template strategy from
https://github.com/MarginOpenSource/strategy-template.

Also check out the official strategies by margin at
https://github.com/MarginOpenSource/official-strategies

## Contributing

Once you created you strategy and would like to share it with the margin community, please follow this
[guide on contributing to open source projects on Github](https://opensource.com/article/19/7/create-pull-request-github).

Specifically for this repository you should put your strategy into a
new file in the folder `margin_community_strategies` and give it a speaking name.

The python file should start with a docstring containing a description of the strategy and its functionality.
Also provide information about any settings that have to be adapted in the strategy before running it.
These should also be in variables on the top that are easily visible for the user and each be described by a doc string.
Please also remove the default documentations from the [strategy template](https://github.com/MarginOpenSource/strategy-template
and add documentation where you deem necessary.
Also remove all functions from the strategy that are not used and don't subscribe to any data that is not required.


## License
The source code is published under the MIT License:

MIT License

Copyright (c) 2019 Margin Open Source

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

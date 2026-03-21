# SVG Hyperlink Test

### 1. Standard Markdown Image
(The most common way. Links usually fail here because it's treated as a static `<img>`.)
![Test SVG](./test_links.svg)

### 2. HTML Image Tag
(Often treated the same as the Markdown version.)
<img src="./test_links.svg" width="300">

### 3. Native Mermaid (For Comparison)
(GitHub renders this server-side using its own engine. Links **do** work here.)

```mermaid
graph LR
    A[Google] --> B[GitHub]
    click A "https://www.google.com" "Open Google"
    click B "https://www.github.com" "Open GitHub"
```

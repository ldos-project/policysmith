# Vieweing results

First, [install MongoDB](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/) on your system and import the `policysmith` results database by running: 

```bash
mongorestore --uri="mongodb://localhost:27017" --archive=policysmith.archive.gz --gzip
```

Then:

1. Use `python3 table.py` to reproduce all data in Table 2 of the paper.
2. Use `python3 boxplot.py --dataset <CloudPhysics|msr>` to reproduce Figures 2(a) and 2(b) from the paper respectively.
3. Use `python3 view_heuristic.py PS-A` to look at Heuristic A discovered by Policysmith (Listing 1 in the paper). Use `PS-B`, `PS-W`, etc to view the other best performing heuristics found. 



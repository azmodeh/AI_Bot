### Hardcoding is forbiden

>  #  I consider those as hardcode
>>
1. Literal String: Any text directly inside *.py file.*

2. Secret,key,Token,Url:** All those has keep under data/config.*

3.  Database:** All query directly inside *.py files.*

4.  Statements:** All statement such as: Print statements,Console statements, log statements, log template,Errors handling.*

>   ## Solution
  
>   -   __All Hardcoded__
>   - *must*  __move__   *in* __Json__ 
>   - *files under:*   __/data/__

>   # Entery:
>>  Main.py must be under Root:/App or Root:/Src and Max: 4 lines allowed
>> 

> # Pep 8:
> *   All       __lines__  must be  ___Under 74 character__
> *   All *.py  __files__  must be  __less than 350 lines__


>  # Cirtical Enforcement:
>  + *.py files must be under Root:/src or Root:/app.
>  + All non py files must be under Root:/data.
>  + Not allowed to create or make something under Project root Directory Exclusive: APP or SRC, Launcher.py, Data
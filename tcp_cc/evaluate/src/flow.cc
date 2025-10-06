//============================================================================
// Author      : Soheil Abbasloo
// Version     : 1.0
//============================================================================

/*
  MIT License
  Copyright (c) Soheil Abbasloo 2020 (ab.soheil@gmail.com)

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
*/

#include "flow.h"


sFlowinfo& sFlowinfo::operator=(const sFlowinfo& other)
{
	if(this != &other)
	{
		Copy(other);
	}
	return *this;
}

void sFlowinfo::Init()
{

	this->flowid=0;
	this->sock=0;
	this->size=0;
	this->rem_size=0;
}
void sFlowinfo::Copy(sFlowinfo info)
{
	this->flowid=info.flowid;
	this->sock=info.sock;
	this->size=info.size;
	this->rem_size=info.rem_size;
}

cFlow::cFlow()
{
	flowinfo.Init();
}

cFlow::cFlow(sFlowinfo info)
{
	flowinfo=info;
}
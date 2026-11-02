
attack/dark-log:     file format elf64-x86-64


Disassembly of section .init:

0000000000401510 <_init>:
  401510:	48 83 ec 08          	sub    rsp,0x8
  401514:	48 8b 05 dd 0a 20 00 	mov    rax,QWORD PTR [rip+0x200add]        # 601ff8 <__gmon_start__>
  40151b:	48 85 c0             	test   rax,rax
  40151e:	74 02                	je     401522 <_init+0x12>
  401520:	ff d0                	call   rax
  401522:	48 83 c4 08          	add    rsp,0x8
  401526:	c3                   	ret

Disassembly of section .plt:

0000000000401530 <.plt>:
  401530:	ff 35 d2 0a 20 00    	push   QWORD PTR [rip+0x200ad2]        # 602008 <_GLOBAL_OFFSET_TABLE_+0x8>
  401536:	ff 25 d4 0a 20 00    	jmp    QWORD PTR [rip+0x200ad4]        # 602010 <_GLOBAL_OFFSET_TABLE_+0x10>
  40153c:	0f 1f 40 00          	nop    DWORD PTR [rax+0x0]

0000000000401540 <puts@plt>:
  401540:	ff 25 d2 0a 20 00    	jmp    QWORD PTR [rip+0x200ad2]        # 602018 <puts@GLIBC_2.2.5>
  401546:	68 00 00 00 00       	push   0x0
  40154b:	e9 e0 ff ff ff       	jmp    401530 <.plt>

0000000000401550 <__stack_chk_fail@plt>:
  401550:	ff 25 ca 0a 20 00    	jmp    QWORD PTR [rip+0x200aca]        # 602020 <__stack_chk_fail@GLIBC_2.4>
  401556:	68 01 00 00 00       	push   0x1
  40155b:	e9 d0 ff ff ff       	jmp    401530 <.plt>

0000000000401560 <printf@plt>:
  401560:	ff 25 c2 0a 20 00    	jmp    QWORD PTR [rip+0x200ac2]        # 602028 <printf@GLIBC_2.2.5>
  401566:	68 02 00 00 00       	push   0x2
  40156b:	e9 c0 ff ff ff       	jmp    401530 <.plt>

0000000000401570 <gets@plt>:
  401570:	ff 25 ba 0a 20 00    	jmp    QWORD PTR [rip+0x200aba]        # 602030 <gets@GLIBC_2.2.5>
  401576:	68 03 00 00 00       	push   0x3
  40157b:	e9 b0 ff ff ff       	jmp    401530 <.plt>

0000000000401580 <fflush@plt>:
  401580:	ff 25 b2 0a 20 00    	jmp    QWORD PTR [rip+0x200ab2]        # 602038 <fflush@GLIBC_2.2.5>
  401586:	68 04 00 00 00       	push   0x4
  40158b:	e9 a0 ff ff ff       	jmp    401530 <.plt>

Disassembly of section .text:

0000000000401590 <_start>:
  401590:	31 ed                	xor    ebp,ebp
  401592:	49 89 d1             	mov    r9,rdx
  401595:	5e                   	pop    rsi
  401596:	48 89 e2             	mov    rdx,rsp
  401599:	48 83 e4 f0          	and    rsp,0xfffffffffffffff0
  40159d:	50                   	push   rax
  40159e:	54                   	push   rsp
  40159f:	49 c7 c0 b0 18 40 00 	mov    r8,0x4018b0
  4015a6:	48 c7 c1 40 18 40 00 	mov    rcx,0x401840
  4015ad:	48 c7 c7 f5 17 40 00 	mov    rdi,0x4017f5
  4015b4:	ff 15 36 0a 20 00    	call   QWORD PTR [rip+0x200a36]        # 601ff0 <__libc_start_main@GLIBC_2.2.5>
  4015ba:	f4                   	hlt
  4015bb:	0f 1f 44 00 00       	nop    DWORD PTR [rax+rax*1+0x0]

00000000004015c0 <_dl_relocate_static_pie>:
  4015c0:	f3 c3                	repz ret
  4015c2:	66 2e 0f 1f 84 00 00 	cs nop WORD PTR [rax+rax*1+0x0]
  4015c9:	00 00 00 
  4015cc:	0f 1f 40 00          	nop    DWORD PTR [rax+0x0]

00000000004015d0 <deregister_tm_clones>:
  4015d0:	55                   	push   rbp
  4015d1:	b8 50 20 60 00       	mov    eax,0x602050
  4015d6:	48 3d 50 20 60 00    	cmp    rax,0x602050
  4015dc:	48 89 e5             	mov    rbp,rsp
  4015df:	74 17                	je     4015f8 <deregister_tm_clones+0x28>
  4015e1:	b8 00 00 00 00       	mov    eax,0x0
  4015e6:	48 85 c0             	test   rax,rax
  4015e9:	74 0d                	je     4015f8 <deregister_tm_clones+0x28>
  4015eb:	5d                   	pop    rbp
  4015ec:	bf 50 20 60 00       	mov    edi,0x602050
  4015f1:	ff e0                	jmp    rax
  4015f3:	0f 1f 44 00 00       	nop    DWORD PTR [rax+rax*1+0x0]
  4015f8:	5d                   	pop    rbp
  4015f9:	c3                   	ret
  4015fa:	66 0f 1f 44 00 00    	nop    WORD PTR [rax+rax*1+0x0]

0000000000401600 <register_tm_clones>:
  401600:	be 50 20 60 00       	mov    esi,0x602050
  401605:	55                   	push   rbp
  401606:	48 81 ee 50 20 60 00 	sub    rsi,0x602050
  40160d:	48 89 e5             	mov    rbp,rsp
  401610:	48 c1 fe 03          	sar    rsi,0x3
  401614:	48 89 f0             	mov    rax,rsi
  401617:	48 c1 e8 3f          	shr    rax,0x3f
  40161b:	48 01 c6             	add    rsi,rax
  40161e:	48 d1 fe             	sar    rsi,1
  401621:	74 15                	je     401638 <register_tm_clones+0x38>
  401623:	b8 00 00 00 00       	mov    eax,0x0
  401628:	48 85 c0             	test   rax,rax
  40162b:	74 0b                	je     401638 <register_tm_clones+0x38>
  40162d:	5d                   	pop    rbp
  40162e:	bf 50 20 60 00       	mov    edi,0x602050
  401633:	ff e0                	jmp    rax
  401635:	0f 1f 00             	nop    DWORD PTR [rax]
  401638:	5d                   	pop    rbp
  401639:	c3                   	ret
  40163a:	66 0f 1f 44 00 00    	nop    WORD PTR [rax+rax*1+0x0]

0000000000401640 <__do_global_dtors_aux>:
  401640:	80 3d 11 0a 20 00 00 	cmp    BYTE PTR [rip+0x200a11],0x0        # 602058 <completed.7698>
  401647:	75 17                	jne    401660 <__do_global_dtors_aux+0x20>
  401649:	55                   	push   rbp
  40164a:	48 89 e5             	mov    rbp,rsp
  40164d:	e8 7e ff ff ff       	call   4015d0 <deregister_tm_clones>
  401652:	c6 05 ff 09 20 00 01 	mov    BYTE PTR [rip+0x2009ff],0x1        # 602058 <completed.7698>
  401659:	5d                   	pop    rbp
  40165a:	c3                   	ret
  40165b:	0f 1f 44 00 00       	nop    DWORD PTR [rax+rax*1+0x0]
  401660:	f3 c3                	repz ret
  401662:	0f 1f 40 00          	nop    DWORD PTR [rax+0x0]
  401666:	66 2e 0f 1f 84 00 00 	cs nop WORD PTR [rax+rax*1+0x0]
  40166d:	00 00 00 

0000000000401670 <frame_dummy>:
  401670:	55                   	push   rbp
  401671:	48 89 e5             	mov    rbp,rsp
  401674:	5d                   	pop    rbp
  401675:	eb 89                	jmp    401600 <register_tm_clones>

0000000000401677 <grade_eval>:
  401677:	55                   	push   rbp
  401678:	48 89 e5             	mov    rbp,rsp
  40167b:	48 83 ec 20          	sub    rsp,0x20
  40167f:	89 7d ec             	mov    DWORD PTR [rbp-0x14],edi
  401682:	64 48 8b 04 25 28 00 	mov    rax,QWORD PTR fs:0x28
  401689:	00 00 
  40168b:	48 89 45 f8          	mov    QWORD PTR [rbp-0x8],rax
  40168f:	31 c0                	xor    eax,eax
  401691:	83 7d ec 04          	cmp    DWORD PTR [rbp-0x14],0x4
  401695:	75 19                	jne    4016b0 <grade_eval+0x39>
  401697:	b8 45 00 00 00       	mov    eax,0x45
  40169c:	2b 45 ec             	sub    eax,DWORD PTR [rbp-0x14]
  40169f:	89 c6                	mov    esi,eax
  4016a1:	bf c8 18 40 00       	mov    edi,0x4018c8
  4016a6:	b8 00 00 00 00       	mov    eax,0x0
  4016ab:	e8 b0 fe ff ff       	call   401560 <printf@plt>
  4016b0:	48 8b 05 99 09 20 00 	mov    rax,QWORD PTR [rip+0x200999]        # 602050 <stdout@GLIBC_2.2.5>
  4016b7:	48 89 c7             	mov    rdi,rax
  4016ba:	e8 c1 fe ff ff       	call   401580 <fflush@plt>
  4016bf:	90                   	nop
  4016c0:	48 8b 45 f8          	mov    rax,QWORD PTR [rbp-0x8]
  4016c4:	64 48 33 04 25 28 00 	xor    rax,QWORD PTR fs:0x28
  4016cb:	00 00 
  4016cd:	74 05                	je     4016d4 <grade_eval+0x5d>
  4016cf:	e8 7c fe ff ff       	call   401550 <__stack_chk_fail@plt>
  4016d4:	c9                   	leave
  4016d5:	c3                   	ret

00000000004016d6 <input>:
  4016d6:	55                   	push   rbp
  4016d7:	48 89 e5             	mov    rbp,rsp
  4016da:	48 81 ec 20 01 00 00 	sub    rsp,0x120
  4016e1:	64 48 8b 04 25 28 00 	mov    rax,QWORD PTR fs:0x28
  4016e8:	00 00 
  4016ea:	48 89 45 f8          	mov    QWORD PTR [rbp-0x8],rax
  4016ee:	31 c0                	xor    eax,eax
  4016f0:	c7 45 e0 00 00 00 00 	mov    DWORD PTR [rbp-0x20],0x0
  4016f7:	bf ed 18 40 00       	mov    edi,0x4018ed
  4016fc:	e8 3f fe ff ff       	call   401540 <puts@plt>
  401701:	48 8d 85 e0 fe ff ff 	lea    rax,[rbp-0x120]
  401708:	48 89 c7             	mov    rdi,rax
  40170b:	e8 60 fe ff ff       	call   401570 <gets@plt>
  401710:	48 85 c0             	test   rax,rax
  401713:	0f 84 c5 00 00 00    	je     4017de <input+0x108>
  401719:	8b 45 e0             	mov    eax,DWORD PTR [rbp-0x20]
  40171c:	48 98                	cdqe
  40171e:	48 8d 95 e0 fe ff ff 	lea    rdx,[rbp-0x120]
  401725:	48 83 ea 80          	sub    rdx,0xffffffffffffff80
  401729:	48 01 d0             	add    rax,rdx
  40172c:	48 8b 95 e0 fe ff ff 	mov    rdx,QWORD PTR [rbp-0x120]
  401733:	48 8b 8d e8 fe ff ff 	mov    rcx,QWORD PTR [rbp-0x118]
  40173a:	48 89 10             	mov    QWORD PTR [rax],rdx
  40173d:	48 89 48 08          	mov    QWORD PTR [rax+0x8],rcx
  401741:	48 8b 95 f0 fe ff ff 	mov    rdx,QWORD PTR [rbp-0x110]
  401748:	48 8b 8d f8 fe ff ff 	mov    rcx,QWORD PTR [rbp-0x108]
  40174f:	48 89 50 10          	mov    QWORD PTR [rax+0x10],rdx
  401753:	48 89 48 18          	mov    QWORD PTR [rax+0x18],rcx
  401757:	48 8b 95 00 ff ff ff 	mov    rdx,QWORD PTR [rbp-0x100]
  40175e:	48 8b 8d 08 ff ff ff 	mov    rcx,QWORD PTR [rbp-0xf8]
  401765:	48 89 50 20          	mov    QWORD PTR [rax+0x20],rdx
  401769:	48 89 48 28          	mov    QWORD PTR [rax+0x28],rcx
  40176d:	48 8b 95 10 ff ff ff 	mov    rdx,QWORD PTR [rbp-0xf0]
  401774:	48 8b 8d 18 ff ff ff 	mov    rcx,QWORD PTR [rbp-0xe8]
  40177b:	48 89 50 30          	mov    QWORD PTR [rax+0x30],rdx
  40177f:	48 89 48 38          	mov    QWORD PTR [rax+0x38],rcx
  401783:	48 8b 95 20 ff ff ff 	mov    rdx,QWORD PTR [rbp-0xe0]
  40178a:	48 8b 8d 28 ff ff ff 	mov    rcx,QWORD PTR [rbp-0xd8]
  401791:	48 89 50 40          	mov    QWORD PTR [rax+0x40],rdx
  401795:	48 89 48 48          	mov    QWORD PTR [rax+0x48],rcx
  401799:	48 8b 95 30 ff ff ff 	mov    rdx,QWORD PTR [rbp-0xd0]
  4017a0:	48 8b 8d 38 ff ff ff 	mov    rcx,QWORD PTR [rbp-0xc8]
  4017a7:	48 89 50 50          	mov    QWORD PTR [rax+0x50],rdx
  4017ab:	48 89 48 58          	mov    QWORD PTR [rax+0x58],rcx
  4017af:	48 8b 95 40 ff ff ff 	mov    rdx,QWORD PTR [rbp-0xc0]
  4017b6:	48 8b 8d 48 ff ff ff 	mov    rcx,QWORD PTR [rbp-0xb8]
  4017bd:	48 89 50 60          	mov    QWORD PTR [rax+0x60],rdx
  4017c1:	48 89 48 68          	mov    QWORD PTR [rax+0x68],rcx
  4017c5:	48 8b 95 50 ff ff ff 	mov    rdx,QWORD PTR [rbp-0xb0]
  4017cc:	48 8b 8d 58 ff ff ff 	mov    rcx,QWORD PTR [rbp-0xa8]
  4017d3:	48 89 50 70          	mov    QWORD PTR [rax+0x70],rdx
  4017d7:	48 89 48 78          	mov    QWORD PTR [rax+0x78],rcx
  4017db:	90                   	nop
  4017dc:	eb 01                	jmp    4017df <input+0x109>
  4017de:	90                   	nop
  4017df:	48 8b 45 f8          	mov    rax,QWORD PTR [rbp-0x8]
  4017e3:	64 48 33 04 25 28 00 	xor    rax,QWORD PTR fs:0x28
  4017ea:	00 00 
  4017ec:	74 05                	je     4017f3 <input+0x11d>
  4017ee:	e8 5d fd ff ff       	call   401550 <__stack_chk_fail@plt>
  4017f3:	c9                   	leave
  4017f4:	c3                   	ret

00000000004017f5 <main>:
  4017f5:	55                   	push   rbp
  4017f6:	48 89 e5             	mov    rbp,rsp
  4017f9:	48 83 ec 10          	sub    rsp,0x10
  4017fd:	64 48 8b 04 25 28 00 	mov    rax,QWORD PTR fs:0x28
  401804:	00 00 
  401806:	48 89 45 f8          	mov    QWORD PTR [rbp-0x8],rax
  40180a:	31 c0                	xor    eax,eax
  40180c:	e8 c5 fe ff ff       	call   4016d6 <input>
  401811:	bf 02 19 40 00       	mov    edi,0x401902
  401816:	e8 25 fd ff ff       	call   401540 <puts@plt>
  40181b:	b8 00 00 00 00       	mov    eax,0x0
  401820:	48 8b 55 f8          	mov    rdx,QWORD PTR [rbp-0x8]
  401824:	64 48 33 14 25 28 00 	xor    rdx,QWORD PTR fs:0x28
  40182b:	00 00 
  40182d:	74 05                	je     401834 <main+0x3f>
  40182f:	e8 1c fd ff ff       	call   401550 <__stack_chk_fail@plt>
  401834:	c9                   	leave
  401835:	c3                   	ret
  401836:	66 2e 0f 1f 84 00 00 	cs nop WORD PTR [rax+rax*1+0x0]
  40183d:	00 00 00 

0000000000401840 <__libc_csu_init>:
  401840:	41 57                	push   r15
  401842:	41 56                	push   r14
  401844:	49 89 d7             	mov    r15,rdx
  401847:	41 55                	push   r13
  401849:	41 54                	push   r12
  40184b:	4c 8d 25 be 05 20 00 	lea    r12,[rip+0x2005be]        # 601e10 <__frame_dummy_init_array_entry>
  401852:	55                   	push   rbp
  401853:	48 8d 2d be 05 20 00 	lea    rbp,[rip+0x2005be]        # 601e18 <__do_global_dtors_aux_fini_array_entry>
  40185a:	53                   	push   rbx
  40185b:	41 89 fd             	mov    r13d,edi
  40185e:	49 89 f6             	mov    r14,rsi
  401861:	4c 29 e5             	sub    rbp,r12
  401864:	48 83 ec 08          	sub    rsp,0x8
  401868:	48 c1 fd 03          	sar    rbp,0x3
  40186c:	e8 9f fc ff ff       	call   401510 <_init>
  401871:	48 85 ed             	test   rbp,rbp
  401874:	74 20                	je     401896 <__libc_csu_init+0x56>
  401876:	31 db                	xor    ebx,ebx
  401878:	0f 1f 84 00 00 00 00 	nop    DWORD PTR [rax+rax*1+0x0]
  40187f:	00 
  401880:	4c 89 fa             	mov    rdx,r15
  401883:	4c 89 f6             	mov    rsi,r14
  401886:	44 89 ef             	mov    edi,r13d
  401889:	41 ff 14 dc          	call   QWORD PTR [r12+rbx*8]
  40188d:	48 83 c3 01          	add    rbx,0x1
  401891:	48 39 dd             	cmp    rbp,rbx
  401894:	75 ea                	jne    401880 <__libc_csu_init+0x40>
  401896:	48 83 c4 08          	add    rsp,0x8
  40189a:	5b                   	pop    rbx
  40189b:	5d                   	pop    rbp
  40189c:	41 5c                	pop    r12
  40189e:	41 5d                	pop    r13
  4018a0:	41 5e                	pop    r14
  4018a2:	41 5f                	pop    r15
  4018a4:	c3                   	ret
  4018a5:	90                   	nop
  4018a6:	66 2e 0f 1f 84 00 00 	cs nop WORD PTR [rax+rax*1+0x0]
  4018ad:	00 00 00 

00000000004018b0 <__libc_csu_fini>:
  4018b0:	f3 c3                	repz ret

Disassembly of section .fini:

00000000004018b4 <_fini>:
  4018b4:	48 83 ec 08          	sub    rsp,0x8
  4018b8:	48 83 c4 08          	add    rsp,0x8
  4018bc:	c3                   	ret
